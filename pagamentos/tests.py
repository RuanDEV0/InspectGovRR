from datetime import date
from decimal import Decimal

import httpx
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from integrations.fiplan_api.client import FiplanClient

from .models import Payment, PaymentSnapshot
from .services import PaymentSyncError, sync_payments

TODAY = date(2026, 2, 20)
CPF = '123.456.789-09'
SEI_LINK = (
    'https://sei.rr.gov.br/sei/processo_acesso_externo_consulta.php'
    '?id_acesso_externo=12345&infra_hash=abcdef0123456789abcdef0123456789'
)


def row(number=20601000126000001, month=1, unit='20601', **extra):
    return {
        'dataPagamento': date(2026, month, 2).isoformat(),
        'valorPagamento': '100.20',
        'codUnidadeOrcamentaria': unit,
        'descUnidadeOrcamentaria': 'Fundo Estadual de Saúde' if unit == '20601' else 'Órgão de teste',
        'codNaturezaDespesa': 33903000,
        'descNaturezaDespesa': 'MATERIAL DE CONSUMO',
        'cpfCnpjCredor': '12345678000199',
        'nomeCredor': 'Empresa de teste',
        'numeroPagamento': number,
        'linkDeAcesso': SEI_LINK,
        'numeroProcesso': '20101.00000001/2026.23',
        **extra,
    }


class FixtureAPI:
    def __init__(self, months, counts=None):
        self.months = months
        self.counts = counts or {}

    def get_payments_export(self, filters):
        month = filters['mesInicio']
        assert filters == {'anoInicio': 2026, 'anoFinal': 2026, 'mesInicio': month, 'mesFinal': month}
        return self.months.get(month, [])

    def get_payments_page(self, filters):
        rows = self.get_payments_export(filters)
        return {'number': 0, 'totalElements': self.counts.get(filters['mesInicio'], len(rows)),
                'content': rows[:1]}


class PaymentClientTests(SimpleTestCase):
    def test_export_renews_token_and_keeps_cents(self):
        calls = []

        def respond(request):
            if request.url.path.endswith('/oauth/token'):
                return httpx.Response(200, json={'access_token': f'token-{len(calls)}'})
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(401)
            return httpx.Response(200, content=b'[{"valorPagamento": 123.45}]')

        with FiplanClient(username='test', password='test', transport=httpx.MockTransport(respond)) as client:
            result = client.get_payments_export({'mesInicio': 1})
        self.assertEqual(result[0]['valorPagamento'], Decimal('123.45'))
        self.assertEqual(calls[1].url.path, '/transparencia/api/v1/pagamento/json')
        self.assertEqual(calls[1].url.params['mesInicio'], '1')
        self.assertEqual(calls[1].headers['Authorization'], 'Bearer token-1')


class PaymentSyncTests(TestCase):
    def test_publishes_complete_months_and_preserves_sign_and_zero(self):
        api = FixtureAPI({
            1: [row(), row(20601000126000002, valorPagamento='0')],
            2: [row(20601000126000003, month=2, valorPagamento='-0.20')],
        })
        snapshot = sync_payments(today=TODAY, client=api)
        self.assertEqual(snapshot.status, PaymentSnapshot.Status.PUBLISHED)
        self.assertEqual(snapshot.total, Decimal('100.00'))
        self.assertEqual(snapshot.record_count, 3)
        second = sync_payments(today=TODAY, client=api)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, PaymentSnapshot.Status.REPLACED)
        self.assertEqual(second.payments.count(), 3)

    def test_truncated_later_month_preserves_last_published_snapshot(self):
        old = sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: [row()]}))
        with self.assertRaisesMessage(PaymentSyncError, 'mês 02'):
            sync_payments(today=TODAY, client=FixtureAPI({1: [row()]}, {2: 2}))
        old.refresh_from_db()
        self.assertEqual(old.status, PaymentSnapshot.Status.PUBLISHED)
        self.assertEqual(Payment.objects.count(), 1)
        failed = PaymentSnapshot.objects.get(status=PaymentSnapshot.Status.FAILED)
        self.assertEqual(failed.record_count, 1)

    def test_refuses_invalid_rows_instead_of_silently_removing_them(self):
        for rows in ([row(), row()], [row(month=2)], [row(valorPagamento='NaN')], [row(valorPagamento='1.001')]):
            with self.subTest(rows=rows), self.assertRaises(PaymentSyncError):
                sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: rows}))
        self.assertFalse(PaymentSnapshot.objects.filter(status=PaymentSnapshot.Status.PUBLISHED).exists())
        self.assertFalse(Payment.objects.exists())

    def test_discards_personal_and_untrusted_fields(self):
        snapshot = sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: [
            row(cpfCnpjCredor=CPF, nomeCredor='Pessoa identificável', descPagamento=CPF),
            row(20601000126000002, linkDeAcesso='https://sei.rr.gov.br.example.org/?cpf=' + CPF),
        ]}))
        person = snapshot.payments.get(creditor_kind='person')
        self.assertEqual((person.creditor_name, person.process, person.process_url), ('', '', ''))
        self.assertEqual(snapshot.payments.get(creditor_kind='company').process_url, '')
        masked = sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: [
            row(cpfCnpjCredor='***.***.***-09', nomeCredor='Pessoa identificável'),
            row(20601000126000002, cpfCnpjCredor='null', nomeCredor='Sem documento'),
        ]}))
        self.assertEqual(list(masked.payments.order_by('number').values_list('creditor_kind', 'creditor_name')),
                         [('person', ''), ('', '')])
        response = self.client.get(reverse('pagamentos:index'))
        self.assertContains(response, 'Pessoa física')
        self.assertContains(response, 'Não informado no registro')
        self.assertNotContains(response, CPF)
        self.assertNotContains(response, 'Pessoa identificável')
        self.assertNotContains(response, 'rr.gov.br.example.org')


class PaymentPageTests(TestCase):
    def test_shows_no_collection_and_invalid_filter_separately(self):
        url = reverse('pagamentos:index')
        self.assertContains(self.client.get(url), 'Ainda não há dados importados')
        self.assertContains(self.client.get(url, {'ano': 'inválido'}), 'Filtro inválido', status_code=400)

    def test_following_health_and_nature_keeps_correct_total_and_source(self):
        sync_payments(today=TODAY, client=FixtureAPI({
            1: [row(), row(13101000126000001, unit='13101', valorPagamento='200.40')],
            2: [row(20601000126000002, month=2, codNaturezaDespesa=33903900,
                    descNaturezaDespesa='SERVIÇOS DE TERCEIROS', valorPagamento='70.00')],
        }))
        url = reverse('pagamentos:index')
        response = self.client.get(url, {'ano': '2026', 'area': 'saude', 'despesa': '33903000'})
        self.assertContains(response, 'Para onde foi o dinheiro público?')
        self.assertContains(response, 'Materiais de consumo')
        self.assertContains(response, 'Consultar processo no SEI')
        self.assertEqual(response.context['total'], Decimal('100.20'))
        self.assertEqual(response.context['record_count'], 1)
        response = self.client.get(url, {'ano': '2026', 'area': 'outros'})
        self.assertEqual(response.context['total'], Decimal('200.40'))
        response = self.client.get(url, {'ano': '2026', 'area': 'saude', 'despesa': '33903000', 'mes': '2'})
        self.assertContains(response, 'Sem registros neste recorte')
        self.assertIsNone(response.context['total'])
        self.assertEqual(self.client.get(url, {'ano': '2026', 'mes': '3'}).status_code, 400)

    def test_failed_update_displays_previous_collection_and_filters_survive_pagination(self):
        records = [row(20601000126000001 + i) for i in range(16)]
        sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: records}))
        with self.assertRaises(PaymentSyncError):
            sync_payments(today=TODAY, client=FixtureAPI({1: records}, {2: 1}))
        response = self.client.get(reverse('pagamentos:index'), {'ano': '2026', 'area': 'saude'})
        self.assertContains(response, 'A última atualização não foi concluída')
        self.assertIn('area=saude', response.context['next_url'])
        self.assertEqual(response.context['record_count'], 16)

    def test_landing_summarizes_state_and_compares_areas(self):
        sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: [
            row(valorPagamento='300.00'),
            row(20601000126000002, codNaturezaDespesa=33913900, descNaturezaDespesa='SERVIÇOS', valorPagamento='100.00'),
            row(20601000126000003, cpfCnpjCredor=CPF, nomeCredor='Pessoa identificável', valorPagamento='900.00',
                codNaturezaDespesa=31901100, descNaturezaDespesa='VENCIMENTOS', descTipoDespesa='Folha de Pagamento'),
            row(13101000126000001, unit='13101', valorPagamento='700.00'),
        ]}))
        url = reverse('pagamentos:index')
        response = self.client.get(url, {'ano': '2026', 'mes': '1'})
        insight = response.context['insight']
        self.assertEqual((insight['days'], insight['per_day'], insight['internal']),
                         (31, Decimal('64.52'), Decimal('100.00')))
        self.assertEqual([part['share'] for part in insight['slices']],
                         [Decimal('50.00'), Decimal('45.00'), Decimal('5.00')])
        self.assertEqual(insight['top'][0].amount, Decimal('900.00'))
        health = response.context['panels'][0]['insight']
        self.assertEqual((health['total'], health['of_state'], health['payroll_share']),
                         (Decimal('1300.00'), Decimal('65.00'), Decimal('69.23')))
        self.assertEqual([(item['creditor_name'], item['total']) for item in health['recipients']],
                         [('Empresa de teste', Decimal('400.00'))])
        self.assertIsNone(response.context['panels'][1]['insight'])
        self.assertContains(response, 'Saúde, segurança e educação')
        self.assertContains(response, 'style="width: 50.00%"')
        self.assertNotContains(response, 'Pessoa identificável')

    def test_area_panel_leads_to_recipient_records_sorted_by_value(self):
        sync_payments(today=TODAY, client=FixtureAPI({
            1: [row(valorPagamento='300.00'), row(20601000126000002, nomeCredor='Outra empresa', valorPagamento='50.00')],
            2: [row(20601000126000003, month=2, valorPagamento='900.00')],
        }))
        url = reverse('pagamentos:index')
        response = self.client.get(url, {'ano': '2026', 'area': 'saude'})
        insight = response.context['insight']
        self.assertEqual([item['total'] for item in insight['months']], [Decimal('350.00'), Decimal('900.00')])
        self.assertEqual(insight['peak_month']['name'], 'Fevereiro')
        self.assertContains(response, 'Quem mais recebeu fora da folha de pagamento?')
        self.assertIn('credor=Empresa+de+teste', insight['recipients'][0]['url'])
        response = self.client.get(url, {'ano': '2026', 'area': 'saude', 'credor': 'Empresa de teste'})
        self.assertIsNone(response.context['insight'])
        self.assertEqual((response.context['total'], response.context['record_count']), (Decimal('1200.00'), 2))
        self.assertEqual([payment.amount for payment in response.context['page']],
                         [Decimal('900.00'), Decimal('300.00')])
        recent = self.client.get(url, {'ano': '2026', 'area': 'todos', 'ordem': 'recentes'})
        self.assertEqual(recent.context['page'][0].amount, Decimal('900.00'))
        self.assertEqual(self.client.get(url, {'ano': '2026', 'ordem': 'x'}).status_code, 400)

    def test_split_is_skipped_when_a_sum_is_negative(self):
        sync_payments(today=TODAY, month_end=1, client=FixtureAPI({1: [
            row(), row(20601000126000002, codNaturezaDespesa=33903900, valorPagamento='-0.20'),
        ]}))
        response = self.client.get(reverse('pagamentos:index'))
        self.assertEqual(response.context['insight']['slices'], [])
        self.assertNotContains(response, 'De cada R$ 100 pagos pelo estado')
