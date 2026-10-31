from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from contratos.models import Contract, ContractDetail, ContractSnapshot
from diarias.models import DailySnapshot, DailyTrip
from integrations.models import CreditorSnapshot, Credor, Daily, SyncRun
from receita_arrecadada.models import RevenueSnapshot
from remuneracoes.models import PayrollSnapshot
from unidades.models import Unit


IMPORTED_MODELS = (
    RevenueSnapshot, PayrollSnapshot, DailySnapshot, DailyTrip,
    ContractSnapshot, Contract, ContractDetail,
    Daily, Credor, CreditorSnapshot, SyncRun,
)


class ImportedDataAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username='admin-test', password='test-password', email='admin@example.test',
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_every_data_app_is_available_in_admin(self):
        for model in (*IMPORTED_MODELS, Unit):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)
                url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_imported_records_cannot_be_edited_through_admin(self):
        snapshot = RevenueSnapshot.objects.create(
            fiscal_year=2026, month_start=1, month_end=10, rows=[],
        )
        model_admin = admin.site._registry[RevenueSnapshot]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None, snapshot))
        self.assertFalse(model_admin.has_delete_permission(None, snapshot))
        change_url = reverse('admin:receita_arrecadada_revenuesnapshot_change', args=(snapshot.pk,))
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {'fiscal_year': 2025}).status_code, 403)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.fiscal_year, 2026)

    def test_staff_with_view_permission_can_inspect_without_editing(self):
        viewer = get_user_model().objects.create_user(username='viewer', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='receita_arrecadada', codename='view_revenuesnapshot',
        ))
        self.client.force_login(viewer)
        list_url = reverse('admin:receita_arrecadada_revenuesnapshot_changelist')
        add_url = reverse('admin:receita_arrecadada_revenuesnapshot_add')
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(self.client.get(add_url).status_code, 403)

    def test_legacy_cpf_and_creditor_identifier_are_hidden(self):
        unit = Unit.objects.create(code='123', name='Órgão de teste')
        daily = Daily.objects.create(
            unit=unit, code_api='VIA-1', recipient_name='Pessoa de teste',
            recipient_cpf='12345678901', date_inicied=date(2026, 1, 1),
            date_return=date(2026, 1, 2), value=Decimal('10.00'),
        )
        run = SyncRun.objects.create(fiscal_year=2026, nature_code='33903900')
        creditor = CreditorSnapshot.objects.create(
            run=run, unit=unit, identifier='98765432100', name='Credor de teste',
            fiscal_year=2026, nature_code='33903900', total_liquidado=Decimal('10.00'),
            total_pago=Decimal('10.00'), quantidade_pagamentos=1,
        )
        for model, obj, sensitive_value in (
            (Daily, daily, '12345678901'),
            (CreditorSnapshot, creditor, '98765432100'),
        ):
            with self.subTest(model=model.__name__):
                url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_change', args=(obj.pk,))
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, sensitive_value)
                list_url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
                self.assertNotContains(self.client.get(list_url), sensitive_value)
