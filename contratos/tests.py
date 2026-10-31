import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from integrations.management.commands.run_sync_scheduler import read_contracts_sync_enabled
from portal.formatting import LOCAL_TIME_ZONE

from .mappers import (
    aggregate, contract_records, normalize_additives, normalize_contracts, normalize_history, normalize_inspectors,
)
from .models import Contract, ContractDetail, ContractSnapshot
from .services import sync_contract_details, sync_contracts
from .views import _growth_label, _percent_label


def contract(contract_id, document='12345678000190', agency='17101', amount='100.00', **extra):
    return {
        'idContrato': contract_id, 'cpfCnpjContratado': document,
        'nomeContratado': f'Empresa {document[-4:]}', 'exercicioContrato': '2026',
        'codigoUnidadeOrcamentaria': agency, 'orgaoContratante': f'Órgão {agency}',
        'valorTotalContrato': amount, 'valorTotalPago': '50.00',
        'valorTotalLiquidado': '60.00', 'valorTotalAditivos': None, 'valorContrato': amount,
        'numeroContratoFormatado': f'{contract_id:06d}/2026', 'objetoDoContrato': 'Serviço de limpeza',
        'tipoContrato': 'Serviços', 'situacaoContrato': 'Ativo',
        'dataInicioVigenciaContrato': '2026-01-01T00:00:00.000Z',
        'dataFimVigenciaContrato': '2026-12-31T00:00:00.000Z',
        'dataFimVigenciaContratoAditivado': '2026-12-31T00:00:00.000Z',
        'numeroProcessoSei': '17101.000001/2026.01',
        'linkProcessoSei': 'https://sei.rr.gov.br/sei/processo_acesso_externo_consulta.php?id_acesso_externo=1',
        **extra,
    }


def additive(contract_id, kind=10038, **extra):
    return {'idContrato': contract_id, 'numrControleTermoAditivo': '1º TA', 'flagTipoAditivo': kind,
            'dataAditivo': '2026-03-10', 'valorAditivo': None, 'valrReajuste': '50.00',
            'valrApostilamento': None, 'dataInicioVigencia': None, 'dataTerminoVigencia': None,
            'justificativa': 'Reajuste anual', **extra}


def inspector(contract_id, name='Maria Fiscal', **extra):
    return {'idenContrato': contract_id, 'nomeFiscalContrato': name, 'cargoFiscal': 'Analista',
            'lotacaoFiscal': 'DIRAF', 'numrMatricula': '999888777', 'numrPortaria': 12,
            'dataPortaria': '2026-02-01', **extra}


def history_row(year, paid='10.00'):
    return {'exercicioContrato': str(year), 'valorTotalPago': paid,
            'valorDoMaiorContrato': '5.00', 'quantidadeDeContratos': 3}


class FakeContractsClient:
    def __init__(self, rows, total=None):
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.calls = []
        self.detail_calls = []
        self.failing = set()

    def get_contract_additives(self, contract_id):
        self.detail_calls.append(('additives', contract_id))
        return [additive(contract_id)]

    def get_contract_inspectors(self, contract_id):
        self.detail_calls.append(('inspectors', contract_id))
        if contract_id in self.failing:
            raise httpx.ConnectError('falha simulada')
        return [inspector(contract_id)]

    def get_contracts(self, start, end):
        self.calls.append((start, end))
        return self.rows

    def get_contracts_page(self, start, end, page=0, size=1):
        return {'content': self.rows[:size], 'totalElements': self.total}

    def get_contract_yearly_totals(self):
        return [history_row(2026), history_row(2025)]


class ContractMapperTests(SimpleTestCase):
    def test_normalize_cleans_names_documents_and_missing_payments(self):
        row = normalize_contracts([contract(
            1, document='1234567000190', nomeContratado='COLET&#1040;  LTDA', valorTotalPago=None,
        )])[0]
        self.assertEqual(row['document'], '01234567000190')
        self.assertEqual(row['name'], 'COLETА LTDA')
        self.assertEqual(str(row['paid']), '0.00')

    def test_invalid_payloads_are_rejected(self):
        invalid = [
            [], {'content': []}, [contract(1), contract(1)],
            [contract(1, amount='NaN')], [contract(1, amount=None)],
            [contract(1, document='123')], [contract(1, orgaoContratante='')],
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize_contracts(payload)

    def test_aggregate_groups_by_supplier_and_agency_share(self):
        rows = [
            contract(1, '11111111000111', '17101', '700.00'),
            contract(2, '11111111000111', '20601', '100.00'),
            contract(3, '22222222000122', '17101', '200.00'),
            contract(4, '33333333000133', '17101', '100.00', exercicioContrato='2024'),
        ]
        data = aggregate(normalize_contracts(rows), 2026)
        leader = data['suppliers'][0]
        self.assertEqual((leader['contracts'], leader['agency_count'], leader['area_count']), (2, 2, 2))
        self.assertEqual(leader['contracted'], '800.00')
        self.assertEqual(leader['dominant'], {'name': 'Órgão 17101', 'percent': '70.0'})
        agency = data['agencies'][0]
        self.assertEqual((agency['code'], agency['supplier_count']), ('17101', 3))
        self.assertEqual([row['percent'] for row in agency['top']], ['70.0', '20.0', '10.0'])
        self.assertEqual(data['summary']['signed_in_year'], 3)
        self.assertEqual(data['summary']['contracted'], '1100.00')

    def test_dominance_needs_competition_and_others_fold_after_top_five(self):
        rows = [contract(1, '11111111000111', '20601', '900.00'), contract(2, '22222222000122', '20601', '100.00')]
        self.assertIsNone(aggregate(normalize_contracts(rows), 2026)['suppliers'][0]['dominant'])
        many = [contract(number, f'{number:014d}', '17101', str(10 - number)) for number in range(1, 8)]
        agency = aggregate(normalize_contracts(many), 2026)['agencies'][0]
        self.assertEqual(len(agency['top']), 5)
        self.assertEqual(agency['others']['count'], 2)

    def test_individual_document_is_masked_and_not_stored(self):
        data = aggregate(normalize_contracts([contract(1, document='12345678901')]), 2026)
        self.assertEqual(data['suppliers'][0]['document'], '***.***.***-01')
        self.assertEqual(data['suppliers'][0]['cnpj'], '')
        self.assertNotIn('12345678901', json.dumps(data))

    def test_records_flag_changes_and_drop_document(self):
        rows = normalize_contracts([
            contract(1, valorTotalAditivos='10.00', linkProcessoSei='#'),
            contract(2, dataFimVigenciaContratoAditivado='2027-06-30T00:00:00.000Z'),
            contract(3),
        ])
        records = contract_records(rows)
        self.assertEqual([record['has_changes'] for record in records], [True, True, False])
        self.assertEqual(records[0]['sei_url'], '')
        self.assertEqual(records[1]['end'], date(2027, 6, 30))
        self.assertNotIn('12345678000190', json.dumps(records, default=str))

    def test_additives_use_api_labels_and_ignore_placeholder_values(self):
        rows = normalize_additives([
            additive(1, kind=10037, valrReajuste=None, valorAditivo='0.01', dataAditivo='2026-05-01',
                     dataInicioVigencia='2026-06-01', dataTerminoVigencia='2027-05-31'),
            additive(1, kind=10036),
            additive(1, kind='10038'),
        ], 1)
        self.assertEqual([row['kind'] for row in rows], ['Outra alteração', 'Acréscimo de valor', 'Prorrogação de prazo'])
        self.assertEqual(rows[1]['amount'], '50.00')
        self.assertIsNone(rows[2]['amount'])
        self.assertEqual(rows[2]['end'], '2027-05-31')
        with self.assertRaises(ValueError):
            normalize_additives([additive(2)], 1)

    def test_inspectors_skip_registration_and_duplicates(self):
        rows = normalize_inspectors([inspector(1), inspector(1), inspector(1, name='')], 1)
        self.assertEqual(len(rows), 1)
        self.assertNotIn('999888777', json.dumps(rows))
        with self.assertRaises(ValueError):
            normalize_inspectors({'content': []}, 1)

    def test_history_drops_future_years_and_rejects_duplicates(self):
        rows = normalize_history([history_row(2027), history_row(2026), history_row(2025)], 2026)
        self.assertEqual([row['year'] for row in rows], [2026, 2025])
        with self.assertRaises(ValueError):
            normalize_history([history_row(2026), history_row(2026)], 2026)


class ContractLabelTests(SimpleTestCase):
    def test_percent_label_uses_comma_and_drops_zero_decimal(self):
        self.assertEqual([_percent_label(value) for value in ('70.0', '6.3', '100.0', '0.0')],
                         ['70%', '6,3%', '100%', '0%'])

    def test_growth_label_ignores_cent_differences(self):
        def growth(original, contracted):
            return _growth_label(Contract(original=Decimal(original), contracted=Decimal(contracted)))
        self.assertEqual(growth('100000.00', '100000.40'), '')
        self.assertEqual(growth('100.00', '125.00'), '+25% sobre o valor assinado')
        self.assertEqual(growth('100.00', '300.00'), '3,0× o valor assinado')
        self.assertEqual(growth('100.00', '90.00'), '')


class ContractSyncTests(TestCase):
    def test_sync_uses_calendar_year_and_saves_snapshot(self):
        client = FakeContractsClient([contract(1), contract(2, '22222222000122')])
        snapshot = sync_contracts(client=client, today=date(2026, 10, 27))
        self.assertEqual(client.calls, [('2026-01-01', '2026-12-31')])
        self.assertEqual(snapshot.summary['suppliers'], 2)
        self.assertEqual(len(snapshot.history), 2)

    def test_incomplete_export_keeps_previous_snapshot(self):
        sync_contracts(client=FakeContractsClient([contract(1)]), year=2026)
        with self.assertRaises(ValueError):
            sync_contracts(client=FakeContractsClient([contract(1), contract(2)], total=3), year=2026)
        self.assertEqual(ContractSnapshot.objects.get().summary['contracts'], 1)

    def test_sync_replaces_contract_rows(self):
        sync_contracts(client=FakeContractsClient([contract(1), contract(2)]), year=2026)
        sync_contracts(client=FakeContractsClient([contract(3)]), year=2026)
        self.assertEqual(list(Contract.objects.values_list('contract_id', flat=True)), [3])

    def test_details_queue_respects_limit_and_refetches_changes(self):
        client = FakeContractsClient([
            contract(1, amount='900.00', valorTotalAditivos='10.00'), contract(2, amount='100.00'),
        ])
        sync_contracts(client=client, year=2026)
        counts = sync_contract_details(2026, client=client, limit=1)
        self.assertEqual(counts, {'updated': 1, 'failed': 0, 'pending': 1})
        self.assertEqual(client.detail_calls, [('additives', 1), ('inspectors', 1)])
        sync_contract_details(2026, client=client)
        self.assertEqual(ContractDetail.objects.count(), 2)

        client.detail_calls.clear()
        self.assertEqual(sync_contract_details(2026, client=client)['updated'], 0)
        client.rows = [contract(1, amount='900.00', valorTotalAditivos='20.00'), contract(2, amount='100.00')]
        sync_contracts(client=client, year=2026)
        sync_contract_details(2026, client=client)
        self.assertEqual(client.detail_calls, [('additives', 1), ('inspectors', 1)])

        later = timezone.now() + timedelta(days=8)
        self.assertEqual(sync_contract_details(2026, client=client, now=later)['updated'], 2)

    def test_details_stop_after_consecutive_failures_and_keep_saved(self):
        rows = [contract(number, amount=str(100 - number)) for number in range(1, 9)]
        client = FakeContractsClient(rows)
        sync_contracts(client=client, year=2026)
        client.failing = set(range(2, 9))
        with self.assertRaisesMessage(ValueError, 'ConnectError'):
            sync_contract_details(2026, client=client)
        self.assertEqual(list(ContractDetail.objects.values_list('contract_id', flat=True)), [1])

    def test_sync_drops_details_of_removed_contracts(self):
        client = FakeContractsClient([contract(1), contract(2)])
        sync_contracts(client=client, year=2026)
        sync_contract_details(2026, client=client)
        client.rows = client.rows[:1]
        client.total = 1
        sync_contracts(client=client, year=2026)
        self.assertEqual(list(ContractDetail.objects.values_list('contract_id', flat=True)), [1])

    def test_scheduler_flag_defaults_to_credentials(self):
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)), patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / '.env'
            path.write_text('FIPLAN_USERNAME=test\nFIPLAN_PASSWORD=test\n')
            self.assertTrue(read_contracts_sync_enabled())
            path.write_text('FIPLAN_CONTRACTS_AUTO_SYNC_ENABLED=False\n')
            self.assertFalse(read_contracts_sync_enabled())


class ContractPageTests(TestCase):
    def setUp(self):
        rows = [
            contract(1, '11111111000111', '17101', '700.00', nomeContratado='Construtora Ação'),
            contract(2, '11111111000111', '20601', '100.00', nomeContratado='Construtora Ação'),
            contract(3, '22222222000122', '17101', '200.00', nomeContratado='Limpeza Norte'),
            contract(4, '12345678901', '17101', '100.00', nomeContratado='Pessoa Física'),
        ]
        sync_contracts(client=FakeContractsClient(rows), year=2026)

    def test_page_reads_local_snapshot(self):
        with patch('integrations.fiplan_api.client.FiplanClient', side_effect=AssertionError('API chamada')):
            response = self.client.get(reverse('contratos:index'))
        self.assertContains(response, 'Nome oficial: <strong>Contratos e aditivos</strong>', html=False)
        self.assertContains(response, 'Fica com 70% do valor contratado por Órgão 17101')
        self.assertContains(response, 'Atende 2 órgãos de 2 áreas')
        self.assertContains(response, 'cnpj=11111111000111')
        self.assertContains(response, 'CPF ***.***.***-01')
        self.assertNotContains(response, '12345678901')

    def test_agency_filter_scopes_values(self):
        response = self.client.get(reverse('contratos:index'), {'orgao': '20601'})
        self.assertContains(response, '1 de 1 fornecedor')
        self.assertContains(response, 'Contratos neste órgão (100% do total)')
        self.assertNotContains(response, 'Limpeza Norte')

    def test_search_ignores_accents_and_accepts_cnpj(self):
        self.assertContains(self.client.get(reverse('contratos:index'), {'busca': 'construtora acao'}), '1 de 1 fornecedor')
        self.assertContains(self.client.get(reverse('contratos:index'), {'busca': '22.222.222'}), 'Limpeza Norte')
        response = self.client.get(reverse('contratos:index'), {'busca': 'nada'})
        self.assertContains(response, 'Nenhum fornecedor encontrado')

    def test_search_term_is_kept_in_supplier_links(self):
        response = self.client.get(reverse('contratos:index'), {'busca': 'valor'})
        self.assertEqual(response.context['query_string'], 'busca=valor')

    def test_unknown_parameters_fall_back_to_defaults(self):
        response = self.client.get(reverse('contratos:index'), {'orgao': 'x', 'ordem': 'y'})
        self.assertContains(response, '3 de 3 fornecedores')

    def test_home_highlights_contracts(self):
        self.assertContains(self.client.get(reverse('home')), 'Contratos com vigência em 2026')


class ContractEmptyPageTests(TestCase):
    def test_empty_page_explains_missing_data(self):
        self.assertContains(self.client.get(reverse('contratos:index')), 'Dados ainda não disponíveis')


class SupplierAndExpiringPageTests(TestCase):
    def setUp(self):
        today = datetime.now(LOCAL_TIME_ZONE).date()
        soon = f'{today + timedelta(days=10)}T00:00:00.000Z'
        rows = [
            contract(1, '11111111000111', '17101', '300.00', nomeContratado='Construtora Ação',
                     valorContrato='100.00', valorTotalAditivos='200.00', valorTotalPago='400.00',
                     dataFimVigenciaContratoAditivado=soon),
            contract(2, '11111111000111', '20601', '100.00', nomeContratado='Construtora Ação',
                     situacaoContrato='Rescindido', dataFimVigenciaContratoAditivado=soon),
            contract(3, '22222222000122', '17101', '50.00', nomeContratado='Limpeza Norte',
                     dataFimVigenciaContratoAditivado='2099-12-31T00:00:00.000Z'),
        ]
        self.client_api = FakeContractsClient(rows)
        snapshot = sync_contracts(client=self.client_api, year=today.year)
        self.supplier_id = snapshot.suppliers[0]['id']

    def test_supplier_page_shows_contracts_before_details(self):
        response = self.client.get(reverse('contratos:supplier', args=[self.supplier_id]))
        self.assertContains(response, 'Construtora Ação')
        self.assertContains(response, '3,0× o valor assinado')
        self.assertContains(response, 'pagamentos acima do valor registrado')
        self.assertContains(response, 'Ainda não coletado')
        self.assertContains(response, 'Abrir o processo no SEI')
        self.assertContains(response, 'Rescindido')
        self.assertNotContains(response, 'Limpeza Norte')

    def test_supplier_page_shows_additives_and_inspectors(self):
        sync_contract_details(datetime.now(LOCAL_TIME_ZONE).year, client=self.client_api)
        response = self.client.get(reverse('contratos:supplier', args=[self.supplier_id]), {'orgao': '17101'})
        self.assertContains(response, 'Maria Fiscal')
        self.assertContains(response, 'Portaria nº 12')
        self.assertContains(response, 'Acréscimo de valor')
        self.assertContains(response, 'Reajuste anual')
        self.assertContains(response, '?orgao=17101#fornecedores')

    def test_unknown_supplier_returns_404(self):
        self.assertEqual(self.client.get(reverse('contratos:supplier', args=['0' * 16])).status_code, 404)

    def test_expiring_lists_only_active_contracts_in_window(self):
        response = self.client.get(reverse('contratos:expiring'))
        self.assertContains(response, 'Vence em 10 dias')
        self.assertContains(response, 'Contrato nº 000001/2026')
        self.assertNotContains(response, 'Contrato nº 000002/2026')
        self.assertNotContains(response, 'Contrato nº 000003/2026')
        self.assertEqual(response.context['count_label'], '1 contrato')
        index = self.client.get(reverse('contratos:index'))
        self.assertContains(index, 'Contratos que vencem nos próximos 90 dias')
        self.assertContains(index, 'O contrato que vence no período soma')

    def test_expiring_page_without_data(self):
        ContractSnapshot.objects.all().delete()
        self.assertContains(self.client.get(reverse('contratos:expiring')), 'Nenhum contrato vence neste período')
