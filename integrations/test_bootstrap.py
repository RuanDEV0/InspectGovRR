"""A carga inicial é retomável e não repete importações concluídas."""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from contratos.models import ContractSnapshot
from contratos.services import local_today
from integrations.models import SyncRun
from receita_arrecadada.models import RevenueSnapshot
from receita_arrecadada.services import current_period
from remuneracoes.models import PayrollSnapshot
from unidades.models import Unit


@override_settings(FIPLAN_USERNAME='test-user', FIPLAN_PASSWORD='test-password')
class InitialLoadTests(TestCase):
    def test_loads_missing_sections_once_and_skips_them_on_restart(self):
        year = current_period()[0]

        def general(**kwargs):
            Unit.objects.create(code='101', name='Unidade de teste')
            SyncRun.objects.create(
                status=SyncRun.Status.SUCCESS,
                fiscal_year=kwargs['fiscal_year'],
                nature_code=kwargs['nature_code'],
            )

        def revenue():
            RevenueSnapshot.objects.create(fiscal_year=year, month_start=1, month_end=1)

        def payroll():
            PayrollSnapshot.objects.create(year=year, month=1)

        def contracts():
            ContractSnapshot.objects.create(fiscal_year=local_today().year)

        with (patch('integrations.management.commands.bootstrap_initial_data.run_sync', side_effect=general) as run,
              patch('integrations.management.commands.bootstrap_initial_data.sync_revenue', side_effect=revenue) as rev,
              patch('integrations.management.commands.bootstrap_initial_data.sync_payroll', side_effect=payroll) as pay,
              patch('integrations.management.commands.bootstrap_initial_data.sync_contracts', side_effect=contracts) as con):
            call_command('bootstrap_initial_data', stdout=StringIO())
            call_command('bootstrap_initial_data', stdout=StringIO())

        for mocked in (run, rev, pay, con):
            self.assertEqual(mocked.call_count, 1)

    def test_failure_keeps_other_sections_and_retries_only_missing_section(self):
        year = current_period()[0]
        revenue_attempts = 0

        def general(**kwargs):
            Unit.objects.create(code='101', name='Unidade de teste')
            SyncRun.objects.create(
                status=SyncRun.Status.SUCCESS,
                fiscal_year=kwargs['fiscal_year'],
                nature_code=kwargs['nature_code'],
            )

        def revenue():
            nonlocal revenue_attempts
            revenue_attempts += 1
            if revenue_attempts == 1:
                raise ValueError('URL sensível')
            RevenueSnapshot.objects.create(fiscal_year=year, month_start=1, month_end=1)

        with (patch('integrations.management.commands.bootstrap_initial_data.run_sync', side_effect=general) as run,
              patch('integrations.management.commands.bootstrap_initial_data.sync_revenue', side_effect=revenue) as rev,
              patch('integrations.management.commands.bootstrap_initial_data.sync_payroll', side_effect=lambda:
                    PayrollSnapshot.objects.create(year=year, month=1)) as pay,
              patch('integrations.management.commands.bootstrap_initial_data.sync_contracts', side_effect=lambda:
                    ContractSnapshot.objects.create(fiscal_year=local_today().year)) as con):
            output = StringIO()
            with self.assertRaises(CommandError):
                call_command('bootstrap_initial_data', stdout=output, stderr=output)
            self.assertNotIn('URL sensível', output.getvalue())
            self.assertEqual(PayrollSnapshot.objects.count(), 1)
            self.assertEqual(ContractSnapshot.objects.count(), 1)
            call_command('bootstrap_initial_data', stdout=StringIO())

        self.assertEqual(RevenueSnapshot.objects.count(), 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(rev.call_count, 2)
        self.assertEqual(pay.call_count, 1)
        self.assertEqual(con.call_count, 1)

    @override_settings(FIPLAN_PASSWORD='')
    def test_missing_credentials_never_starts_import(self):
        with patch('integrations.management.commands.bootstrap_initial_data.run_sync') as run:
            with self.assertRaises(CommandError):
                call_command('bootstrap_initial_data', stdout=StringIO(), stderr=StringIO())
        run.assert_not_called()
