"""Fluxos de importação e configuração que protegem a consistência do portal."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from integrations.management.commands.run_sync_scheduler import read_revenue_sync_enabled, read_sync_config
from integrations.models import CreditorSnapshot, Daily, SyncRun
from integrations.sync.creditors import PAGE_SIZE, sync_creditors
from integrations.sync.dailies import sync_dailies
from integrations.sync.runner import run_sync
from integrations.selectors import top_creditors
from unidades.models import Unit


class FakeFiplanClient:
    def __init__(self):
        self.total_pago = '100.00'

    def get_units(self):
        return [{
            'codigoUnidadeOrcamentaria': '101',
            'descricaoUnidadeOrcamentaria': 'Unidade de teste',
            'sigla': 'UT',
        }]

    def get_creditor_stats(self, unit_code, fiscal_year, nature_code, page, page_size):
        return {'listaCredores': [{
            'identificacaoCredor': '12345678000190',
            'credor': 'Empresa de teste',
            'totalPago': self.total_pago,
            'totalLiquidado': '120.00',
            'quantidadePagamentos': 2,
        }]}

    def get_dailies(self):
        return {'content': [{
            'idDiaria': 'D-1',
            'codUnidadeOrcamentaria': '101',
            'nomeCredor': 'Pessoa de teste',
            'cpf': '12345678901',
            'dataInicio': '2026-01-10',
            'dataRetorno': '2026-01-12',
            'valor': '50.00',
        }]}


class SyncTests(TestCase):
    def test_repeated_sync_replaces_snapshot_without_doubling_total(self):
        client = FakeFiplanClient()
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)
        client.total_pago = '150.00'
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)

        self.assertEqual(Unit.objects.count(), 1)
        self.assertEqual(CreditorSnapshot.objects.count(), 2)
        ranking, legacy = top_creditors(2026, '33903900')
        self.assertFalse(legacy)
        self.assertEqual(ranking[0]['total_pago'], 'R$ 150,00')
        self.assertEqual(SyncRun.objects.filter(status=SyncRun.Status.SUCCESS).count(), 2)

    def test_invalid_second_page_preserves_previous_snapshot(self):
        client = FakeFiplanClient()
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)

        def repeated_page(*args):
            item = client.get_creditor_stats_original(*args)['listaCredores'][0]
            return {'listaCredores': [
                {**item, 'identificacaoCredor': f'{index:014d}'}
                for index in range(PAGE_SIZE)
            ]}

        client.get_creditor_stats_original = client.get_creditor_stats
        client.get_creditor_stats = repeated_page
        with self.assertRaises(ValueError):
            sync_creditors(client, SyncRun.objects.first(), 2026, '33903900')
        self.assertEqual(CreditorSnapshot.objects.count(), 1)

    def test_failed_run_keeps_last_complete_ranking(self):
        client = FakeFiplanClient()
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)
        client.get_creditor_stats = lambda *args: {'erro': 'resposta incompleta'}

        with self.assertRaises(ValueError):
            run_sync(fiscal_year=2026, nature_code='33903900', client=client)

        ranking, legacy = top_creditors(2026, '33903900')
        self.assertFalse(legacy)
        self.assertEqual(ranking[0]['total_pago'], 'R$ 100,00')
        self.assertEqual(SyncRun.objects.filter(status=SyncRun.Status.FAILED).count(), 1)

    def test_optional_dailies_use_stable_id_and_update_existing_row(self):
        client = FakeFiplanClient()
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)
        sync_dailies(client)
        sync_dailies(client)
        self.assertEqual(Daily.objects.count(), 1)
        self.assertEqual(Daily.objects.get().unit.code, '101')
        self.assertNotIn('12345678901', self.client.get('/integrations/get-dailies').content.decode())

    def test_public_views_read_local_data(self):
        client = FakeFiplanClient()
        run_sync(fiscal_year=2026, nature_code='33903900', client=client)
        with patch('integrations.fiplan_api.client.FiplanClient', side_effect=AssertionError('API chamada')):
            self.assertEqual(self.client.get('/unidades/').status_code, 200)
            self.assertRedirects(self.client.get('/integrations/get-units'), '/unidades/', status_code=301)
            self.assertEqual(self.client.get('/integrations/get-list-credor').status_code, 200)
            self.assertEqual(self.client.get('/integrations/get-dailies').status_code, 200)
            self.assertEqual(self.client.get('/integrations/get-token').status_code, 404)
        self.assertEqual(CreditorSnapshot.objects.count(), 1)


class SchedulerConfigTests(SimpleTestCase):
    def test_env_changes_toggle_sync_and_interval_without_restart(self):
        with TemporaryDirectory() as folder:
            env_file = Path(folder) / '.env'
            env_file.write_text('FIPLAN_AUTO_SYNC_ENABLED=False\nFIPLAN_SYNC_INTERVAL_MINUTES=60\n')
            with override_settings(BASE_DIR=Path(folder)), patch.dict(os.environ, {}, clear=False):
                self.assertEqual(read_sync_config()[:2], (False, 60))
                env_file.write_text('FIPLAN_AUTO_SYNC_ENABLED=True\nFIPLAN_SYNC_INTERVAL_MINUTES=5\n')
                self.assertEqual(read_sync_config()[:2], (True, 5))

    def test_revenue_sync_is_independent_and_can_be_paused(self):
        with TemporaryDirectory() as folder:
            env_file = Path(folder) / '.env'
            env_file.write_text('FIPLAN_USERNAME=user\nFIPLAN_PASSWORD=password\nFIPLAN_AUTO_SYNC_ENABLED=False\n')
            with override_settings(BASE_DIR=Path(folder)), patch.dict(os.environ, {}, clear=True):
                self.assertTrue(read_revenue_sync_enabled())
                env_file.write_text('FIPLAN_REVENUE_AUTO_SYNC_ENABLED=False\n')
                self.assertFalse(read_revenue_sync_enabled())
