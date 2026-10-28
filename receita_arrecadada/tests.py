from datetime import date
from unittest.mock import patch

from django.test import TestCase

from unidades.models import Unit

from .models import RevenueSnapshot
from .services import sync_revenue


class FakeRevenueClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_top_revenue_units(self, fiscal_year, month_start, month_end, top):
        self.calls.append((fiscal_year, month_start, month_end, top))
        return self.rows


def revenue_row(code, amount):
    return {
        'codUnidadeOrcamentaria': code,
        'descUnidadeOrcamentaria': f'Unidade {code}',
        'codExercicio': 2026,
        'valorRealizacaoMes': amount,
    }


class RevenueDashboardTests(TestCase):
    def test_sync_sorts_and_limits_response_even_when_api_ignores_top(self):
        client = FakeRevenueClient([
            revenue_row(1, 100), revenue_row(2, 700), revenue_row(3, 300),
            revenue_row(4, 500), revenue_row(5, 200), revenue_row(6, 600),
        ])

        snapshot = sync_revenue(client=client, today=date(2026, 10, 27))

        self.assertEqual(client.calls, [(2026, 1, 10, 5)])
        self.assertEqual([row['unit_code'] for row in snapshot.rows], ['2', '6', '4', '3', '5'])
        self.assertEqual(snapshot.rows[0]['amount'], '700.00')

    def test_invalid_response_keeps_previous_snapshot(self):
        client = FakeRevenueClient([revenue_row(1, 100)])
        sync_revenue(client=client, today=date(2026, 10, 27))
        client.rows = [revenue_row(1, 'not-a-number')]

        with self.assertRaises(ValueError):
            sync_revenue(client=client, today=date(2026, 10, 27))

        self.assertEqual(RevenueSnapshot.objects.get().rows[0]['amount'], '100.00')

    def test_public_page_uses_local_snapshot_and_unit_acronym(self):
        Unit.objects.create(code='2', acronym='UO', name='Unidade de exemplo')
        RevenueSnapshot.objects.create(
            fiscal_year=2026,
            month_start=1,
            month_end=10,
            rows=[{'unit_code': '2', 'unit_name': 'Unidade de exemplo', 'amount': '1400000.00'}],
        )

        with patch('integrations.fiplan_api.client.FiplanClient', side_effect=AssertionError('API chamada')):
            response = self.client.get('/receita-arrecadada/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unidade de exemplo')
        self.assertContains(response, 'R$ 1,4 milhão')
        self.assertContains(response, 'R$ 1.400.000,00')
        self.assertContains(response, 'Os 5 órgãos que mais arrecadaram')
        self.assertContains(response, 'UO')

    def test_empty_page_explains_missing_data(self):
        response = self.client.get('/receita-arrecadada/')
        self.assertContains(response, 'Dados ainda não disponíveis')
