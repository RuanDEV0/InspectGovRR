import copy
import json
import os
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from integrations.fiplan_api.client import FiplanClient
from integrations.management.commands.run_sync_scheduler import read_payroll_sync_enabled
from portal.formatting import brl

from .mappers import normalize_details, normalize_ranking, present_row
from .models import PayrollSnapshot
from .services import fetch_details, recent_periods, sync_payroll


def ranking_row(number=1, amount='16210.00', year=2026, month=8):
    return {'ano': year, 'mes': month, 'nome': f'Pessoa de teste {number}',
            'cpf': f'{number:011d}', 'orgao': f'Órgão {number}', 'valorTotalBruto': amount}


def detail_row(number=1, year=2026, month=8):
    membership = {'matricula': '001', 'orgao': f'Órgão {number}', 'cargo': 'Professor', 'tipoCargo': 'Efetivo', 'nivel': 'A'}
    return {
        'ano': year, 'mes': month, 'cpf': f'{number:011d}', 'nome': f'Pessoa de teste {number}',
        'orgao': f'Órgão {number}', 'cargo': 'Professor',
        'matriculas': [membership, membership.copy(), {**membership, 'matricula': '002', 'cargo': 'Analista'}],
        'vencimento': '10000', 'proventosDiversos': '6210',
        'deducoesObrigatorias': '2000', 'deducoesAutorizadas': None,
        'remuneracaoBruta': '16210', 'remuneracaoLiquida': '14210',
        'lancamentos': [{'evento': 'Vencimento mensal', 'tipoEvento': 'P', 'valor': '10000'}],
    }


def detail_page(content, page=0, pages=1, total=None):
    return {'content': content, 'number': page, 'totalPages': pages,
            'totalElements': len(content) if total is None else total}


class FakePayrollClient:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [ranking_row()]
        self.calls = []
        self.detail_calls = []

    def get_payroll_ranking(self, year, month, limit):
        self.calls.append((year, month, limit))
        return copy.deepcopy(self.rows) if (year, month) == (2026, 8) else []

    def get_payroll_details(self, year, month, cpf, page=0, size=100):
        self.detail_calls.append((year, month, cpf, page, size))
        return detail_page([detail_row(int(cpf), year, month)])


class PayrollMapperTests(SimpleTestCase):
    def test_sort_limit_and_period_validation(self):
        rows = normalize_ranking([ranking_row(number, str(number)) for number in range(1, 56)], 2026, 8)
        self.assertEqual(len(rows), 50)
        self.assertEqual(rows[0]['amount'], '55.00')
        self.assertEqual(rows[-1]['position'], 50)
        with self.assertRaises(ValueError):
            normalize_ranking([ranking_row(month=7)], 2026, 8)

    def test_invalid_money_and_duplicate_rows_are_rejected(self):
        for value in ['NaN', 'Infinity', None, 'not-money']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_ranking([ranking_row(amount=value)], 2026, 8)
        with self.assertRaises(ValueError):
            normalize_ranking([ranking_row(), ranking_row()], 2026, 8)

    def test_minimum_wage_is_bound_to_year_and_rounded(self):
        self.assertEqual(present_row({'amount': '16210.00'}, 2026)['equivalent'], '10,0')
        self.assertEqual(present_row({'amount': '20000.00'}, 2026)['equivalent'], '12,3')
        self.assertIsNone(present_row({'amount': '16210.00'}, 2027)['equivalent'])
        self.assertIsNone(present_row({'amount': '-10.00'}, 2026)['equivalent'])
        self.assertEqual(brl(None), 'Não informado')

    def test_memberships_deduplicate_by_registration_and_agency(self):
        record = detail_row()
        record['matriculas'].append({**record['matriculas'][0], 'orgao': 'Outro órgão'})
        result = normalize_details([record], '00000000001', 2026, 8)
        self.assertEqual(result['membership_count'], 3)
        self.assertIsNone(result['statements'][0]['authorized'])
        self.assertNotIn('00000000001', json.dumps(result))

    def test_wrong_person_and_wrong_period_are_rejected(self):
        for record in [detail_row(number=2), detail_row(month=7)]:
            with self.assertRaises(ValueError):
                normalize_details([record], '00000000001', 2026, 8)

    def test_masked_cpf_requires_matching_middle_digits_and_full_name(self):
        record = {**detail_row(), 'cpf': '##456.789##'}
        self.assertEqual(normalize_details([record], '12345678901', 2026, 8, 'Pessoa de teste 1')['membership_count'], 2)
        for cpf, name in [('12311178901', 'Pessoa de teste 1'), ('12345678901', 'Outra pessoa'), ('12345678901', None)]:
            with self.subTest(cpf=cpf, name=name), self.assertRaises(ValueError):
                normalize_details([record], cpf, 2026, 8, name)

    def test_period_search_crosses_year_boundary(self):
        periods = list(recent_periods(date(2026, 1, 4)))
        self.assertEqual(periods[:2], [(2026, 1), (2025, 12)])
        self.assertEqual(len(periods), 12)

    def test_pagination_is_complete_and_repeated_page_rejected(self):
        client = FakePayrollClient()
        with patch.object(client, 'get_payroll_details', side_effect=[
            detail_page([detail_row()], pages=2, total=2),
            detail_page([{**detail_row(), 'cargo': 'Outro cargo'}], page=1, pages=2, total=2),
        ]):
            self.assertEqual(len(fetch_details(client, 2026, 8, '00000000001')['statements']), 2)
        with patch.object(client, 'get_payroll_details', side_effect=[
            detail_page([detail_row()], pages=2, total=2),
            detail_page([detail_row()], page=1, pages=2, total=2),
        ]), self.assertRaises(ValueError):
            fetch_details(client, 2026, 8, '00000000001')

    def test_missing_detail_is_empty_not_zero(self):
        client = FakePayrollClient()
        with patch.object(client, 'get_payroll_details', return_value=detail_page([], pages=0)):
            self.assertEqual(fetch_details(client, 2026, 8, '00000000001')['statements'], [])

    def test_incomplete_or_excessive_pagination_is_rejected(self):
        client = FakePayrollClient()
        for response in [detail_page([detail_row()], total=2), detail_page([], pages=11), {'content': []}]:
            with patch.object(client, 'get_payroll_details', return_value=response), self.assertRaises(ValueError):
                fetch_details(client, 2026, 8, '00000000001')


class PayrollDashboardTests(TestCase):
    def setUp(self):
        self.api = FakePayrollClient()

    def sync(self):
        return sync_payroll(client=self.api, today=date(2026, 10, 27))

    def test_sync_falls_back_to_latest_available_and_excludes_cpf(self):
        snapshot = self.sync()
        self.assertEqual(self.api.calls, [(2026, 10, 50), (2026, 9, 50), (2026, 8, 50)])
        self.assertEqual((snapshot.year, snapshot.month), (2026, 8))
        self.assertNotIn('00000000001', json.dumps(snapshot.rows))
        self.assertNotIn('_cpf', json.dumps(snapshot.rows))
        self.assertEqual(snapshot.rows[0]['membership_count'], 2)

    def test_repeat_sync_preserves_ids_and_updates_without_duplicates(self):
        snapshot = self.sync()
        record_id = snapshot.rows[0]['id']
        self.api.rows[0]['valorTotalBruto'] = '20000'
        snapshot = self.sync()
        self.assertEqual(PayrollSnapshot.objects.count(), 1)
        self.assertEqual(snapshot.rows[0]['id'], record_id)
        self.assertEqual(snapshot.rows[0]['amount'], '20000.00')

    def test_detail_failure_keeps_previous_snapshot(self):
        snapshot = self.sync()
        self.api.rows[0]['valorTotalBruto'] = '99999'
        with patch.object(self.api, 'get_payroll_details', side_effect=ValueError('Falha')):
            with self.assertRaises(ValueError):
                self.sync()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.rows[0]['amount'], '16210.00')

    def test_empty_period_does_not_overwrite_snapshot(self):
        self.sync()
        self.api.rows = []
        with self.assertRaises(ValueError):
            sync_payroll(client=self.api, year=2026, month=8)
        self.assertEqual(PayrollSnapshot.objects.get().rows[0]['amount'], '16210.00')

    def test_public_pages_use_only_local_data_and_opaque_routes(self):
        snapshot = self.sync()
        detail_url = reverse('remuneracoes:detail', args=[2026, 8, snapshot.rows[0]['id']])
        with patch('integrations.fiplan_api.client.FiplanClient._get', side_effect=AssertionError('API chamada')):
            response = self.client.get('/remuneracoes/')
            self.assertContains(response, 'Agosto de 2026')
            self.assertContains(response, 'R$ 16.210,00')
            self.assertContains(response, '10,0 salários mínimos')
            self.assertContains(response, detail_url)
            self.assertNotContains(response, '00000000001')
            response = self.client.get(detail_url)
            self.assertContains(response, 'Vencimento mensal')
            self.assertContains(response, 'Não informado')
            self.assertNotContains(response, '00000000001')
            self.assertNotContains(response, 'Acima do Teto')

    def test_filters_cover_stored_ranking_and_keep_position(self):
        self.api.rows = [ranking_row(1), ranking_row(2, '20000')]
        self.sync()
        response = self.client.get('/remuneracoes/', {'orgao': 'Órgão 1', 'multiplas': '1'})
        self.assertContains(response, 'Pessoa de teste 1')
        self.assertNotContains(response, 'Pessoa de teste 2')
        self.assertEqual(response.context['rows'][0]['position'], 2)
        self.assertEqual(response.context['total_count'], 2)

    def test_missing_and_invalid_periods_are_explicit(self):
        self.sync()
        response = self.client.get('/remuneracoes/', {'ano': 2026, 'mes': 10})
        self.assertContains(response, 'Dados ainda não disponíveis')
        self.assertNotContains(response, 'Pessoa de teste')
        response = self.client.get('/remuneracoes/', {'mes': 'invalid'})
        self.assertContains(response, 'Selecione um ano e um mês válidos')

    def test_mismatch_between_ranking_and_details_is_identified(self):
        self.api.rows[0]['valorTotalBruto'] = '20000'
        snapshot = self.sync()
        response = self.client.get(reverse('remuneracoes:detail', args=[2026, 8, snapshot.rows[0]['id']]))
        self.assertContains(response, 'O total bruto do detalhamento difere')
        self.assertContains(response, 'R$ 20.000,00')
        self.assertContains(response, 'R$ 16.210,00')

    def test_unknown_detail_is_404_and_source_text_is_escaped(self):
        self.api.rows[0]['nome'] = '<script>alert(1)</script>'
        snapshot = self.sync()
        self.assertContains(self.client.get('/remuneracoes/'), '&lt;script&gt;')
        response = self.client.get(reverse('remuneracoes:detail', args=[2026, 7, snapshot.rows[0]['id']]))
        self.assertEqual(response.status_code, 404)


class PayrollIntegrationTests(SimpleTestCase):
    def test_http_parameters_and_paths(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'access_token': 'test-token'} if request.method == 'POST' else [])

        with FiplanClient(username='test', password='test', transport=httpx.MockTransport(handler)) as client:
            client.get_payroll_ranking(2026, 8)
            client.get_payroll_details(2026, 8, '00000000001', page=2)
        self.assertEqual(requests[1].url.path, '/transparencia/api/v1/remuneracoes/rankingTotalBruto')
        self.assertEqual(dict(requests[1].url.params), {'ano': '2026', 'mes': '8', 'limit': '50'})
        self.assertEqual(requests[2].url.params['page'], '2')
        self.assertEqual(requests[2].url.params['size'], '100')

    def test_scheduler_flag_is_independent(self):
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)), patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            path.write_text('FIPLAN_USERNAME=test\nFIPLAN_PASSWORD=test\nFIPLAN_AUTO_SYNC_ENABLED=False\n')
            self.assertTrue(read_payroll_sync_enabled())
            path.write_text('FIPLAN_PAYROLL_AUTO_SYNC_ENABLED=False\n')
            self.assertFalse(read_payroll_sync_enabled())
