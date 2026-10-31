from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

from portal.formatting import count, quantity

from .destinations import ABROAD, BRAZIL, RORAIMA, UNKNOWN, classify
from .mappers import aggregate, clean_reason, classify_reason, normalize, reconcile
from .models import DailySnapshot, DailyTrip
from .services import sync_dailies
from .views import map_shapes

ITEM = {
    'cdExercicio': 2026, 'cpfCnpjCredor': '123.456.789-09', 'numeroEmpenho': '35101000126001481',
    'nomeCredor': 'Pessoa de teste', 'cdUnidadeOrcamentaria': '101', 'sigla': 'ORG ',
    'dsUnidadeOrcamentaria': ' Órgão de teste', 'cargo': 'Analista', 'matricula': '999',
    'dataInicioViagem': '2026-04-15', 'dataRetornoViagem': '2026-04-20',
    'localidade': 'Rorainópolis/RR', 'motivo': 'Prestar serviços de fiscalização no posto fiscal do Jundiá',
    'valorEmpenho': 1080, 'totalPago': 1080, 'totalEstornado': 0, 'valrOsd': '1080',
    'quantidadeDiarias': '4.5', 'valorDiaria': 240, 'numrProcessoFormatado': '001057/26-10',
    'link': 'https://sei.rr.gov.br/sei/processo_acesso_externo_consulta.php?id=1',
}
LUMP = {
    'cdExercicio': 2026, 'cpfCnpjCredor': '84012533000183', 'numeroEmpenho': '25101000126000041',
    'nomeCredor': 'MINISTERIO PUBLICO', 'cdUnidadeOrcamentaria': '25101', 'sigla': 'MPE',
    'dsUnidadeOrcamentaria': 'Ministério Público ', 'valorEmpenho': 1575000, 'totalPago': 1009569.48,
    'totalEstornado': 0, 'dataInicioViagem': None, 'dataRetornoViagem': None,
}
OFFICIAL = [{'sigla': 'ORG', 'totalPago': 1080}]


def api(export, *, total=None, units=(), by_unit=None, official=OFFICIAL):
    class API:
        calls = []

        def get_new_dailies(self, year, page, size, unit=None):
            self.calls.append(('list', unit))
            if unit is None:
                return {'totalElements': len(export) if total is None else total, 'totalPages': 1, 'content': []}
            rows = (by_unit or {}).get(unit, [])
            return {'totalElements': len(rows), 'totalPages': 1 if rows else 0, 'content': rows}

        def get_dailies_export(self, year):
            return export

        def get_units(self):
            return [{'codigoUnidadeOrcamentaria': code} for code in units]

        def get_dailies_agency_totals(self, year):
            return official
    return API()


class DestinationTests(SimpleTestCase):
    def test_spellings_become_the_same_place(self):
        for text in ('RORAINOPOLIS-RR', 'Rorainópolis/RR', 'BV - RORAINÓPOLIS - BV', 'Posto do Jundiá'):
            self.assertEqual(classify(text), (RORAIMA, ['Rorainópolis']), text)

    def test_route_keeps_every_stop_but_not_the_departure(self):
        self.assertEqual(classify('Boa Vista - Caroebe e São Luiz/RR')[1], ['Caroebe', 'São Luiz'])
        self.assertEqual(classify('Boa Vista/RR'), (RORAIMA, ['Boa Vista']))

    def test_region_of_roraima_is_not_the_capital_of_acre(self):
        scope, places = classify('BAIXO RIO BRANCO - RR')
        self.assertEqual(scope, RORAIMA)
        self.assertNotIn('Rio Branco/AC', places)

    def test_city_named_like_a_country_stays_in_brazil(self):
        self.assertEqual(classify('BOA VISTA/RR - NOVA LIMA/MG- BOA VISTA/RR'), (BRAZIL, ['Nova Lima/MG']))

    def test_foreign_destination_wins_over_the_departure(self):
        self.assertEqual(classify('Boa Vista - RR / Madrid/Espanha'), (ABROAD, ['Espanha']))

    def test_unknown_text_is_not_guessed(self):
        self.assertEqual(classify('MARACA'), (UNKNOWN, []))


class NormalizationTests(SimpleTestCase):
    def test_payment_quantity_and_identity(self):
        row = normalize(ITEM, 2026)
        self.assertEqual(row['paid'], Decimal('1080.00'))
        self.assertEqual(row['quantity'], Decimal('4.50'))
        self.assertTrue(row['formula_ok'])
        self.assertEqual(row['status'], 'paid')
        self.assertEqual((row['acronym'], row['agency']), ('ORG', 'Órgão de teste'))

    def test_personal_identifiers_do_not_leave_the_mapper(self):
        row = normalize(ITEM, 2026)
        self.assertNotIn('12345678909', str(row))
        self.assertNotIn('123.456.789-09', str(row))
        self.assertNotIn('matricula', row)

    def test_institution_is_a_lump_sum_not_a_person(self):
        row = normalize(LUMP, 2026)
        self.assertEqual(row['kind'], 'lump_sum')
        self.assertEqual(row['paid'], Decimal('1009569.48'))

    def test_unpaid_trips_are_told_apart(self):
        self.assertEqual(normalize({**ITEM, 'totalPago': 0, 'totalEstornado': 900}, 2026)['status'], 'reversed')
        self.assertEqual(normalize({**ITEM, 'totalPago': 0}, 2026)['status'], 'pending')

    def test_source_quantity_that_does_not_close_is_flagged(self):
        self.assertFalse(normalize({**ITEM, 'quantidadeDiarias': '75', 'valorDiaria': 12, 'valrOsd': '900.5'}, 2026)['formula_ok'])

    def test_unreadable_quantity_becomes_not_informed(self):
        row = normalize({**ITEM, 'quantidadeDiarias': 'n/d'}, 2026)
        self.assertIsNone(row['quantity'])
        self.assertFalse(row['formula_ok'])

    def test_external_link_is_restricted_to_sei(self):
        self.assertEqual(normalize({**ITEM, 'link': '#'}, 2026)['sei_url'], '')
        self.assertEqual(normalize({**ITEM, 'link': 'https://exemplo.com/x'}, 2026)['sei_url'], '')

    def test_incomplete_or_divergent_records_fail(self):
        for change in ({'cpfCnpjCredor': None}, {'totalPago': None}, {'totalPago': 'NaN'}, {'cdExercicio': 2025},
                       {'dataRetornoViagem': '2026-04-01'}, {'dataInicioViagem': 'ontem'}):
            with self.assertRaises(ValueError):
                normalize({**ITEM, **change}, 2026)

    def test_reason_is_cleaned_without_being_rewritten(self):
        self.assertEqual(clean_reason('Remoção&#8203; de  pacientes.'), 'Remoção de pacientes.')
        self.assertEqual(clean_reason('ENTREGA DE CESTAS EM BOA VISTA/RR'), 'Entrega de cestas em Boa Vista/RR')

    def test_event_is_not_counted_as_inspection(self):
        self.assertEqual(classify_reason('Participar do congresso de fiscalização'), 'eventos')
        self.assertEqual(classify_reason('Realizar vistoria em obra pública'), 'obras-ambiente')
        self.assertEqual(classify_reason('Tratar de assuntos institucionais'), 'outros')


class SummaryTests(SimpleTestCase):
    def test_total_includes_lump_sum_but_people_and_places_do_not(self):
        summary = aggregate([normalize(ITEM, 2026)], [normalize(LUMP, 2026)], reconciled=1)
        self.assertEqual(summary['paid'], '1010649.48')
        self.assertEqual(summary['detailed_paid'], '1080.00')
        self.assertEqual(summary['people']['count'], 1)
        self.assertEqual(summary['places'][RORAIMA][0]['paid'], '1080.00')
        self.assertTrue(next(row for row in summary['agencies'] if row['acronym'] == 'MPE')['lump_sum'])

    def test_highlight_avoids_names_and_private_properties(self):
        trip = normalize({**ITEM, 'motivo': 'Vistoria in loco no Sítio de um produtor da região de Normandia'}, 2026)
        summary = aggregate([trip], [], reconciled=1)
        self.assertIsNone(summary['places'][RORAIMA][0]['example'])
        self.assertEqual(summary['featured'], [])

    def test_place_example_comes_from_the_most_common_reason(self):
        same_team = {**ITEM, 'numeroEmpenho': '2'}
        health = {**ITEM, 'numeroEmpenho': '3', 'motivo': 'Realizar atendimento de saúde na unidade básica do município'}
        trips = [normalize(item, 2026) for item in (ITEM, same_team, health)]
        example = aggregate(trips, [], reconciled=1)['places'][RORAIMA][0]['example']
        self.assertEqual(example['theme'], trips[0]['theme'])
        self.assertNotEqual(example['theme'], trips[2]['theme'])

    def test_reconciliation_rejects_a_divergent_total(self):
        trip = normalize(ITEM, 2026)
        self.assertEqual(reconcile([trip], [], OFFICIAL), 1)
        with self.assertRaises(ValueError):
            reconcile([trip], [], [{'sigla': 'ORG', 'totalPago': 1081}])
        with self.assertRaises(ValueError):
            reconcile([trip], [], [])


class FormattingTests(SimpleTestCase):
    def test_counts_and_quantities(self):
        self.assertEqual(count(14232), '14.232')
        self.assertEqual(count('55102.75'), '55.103')
        self.assertEqual(quantity('7.50'), '7,5')
        self.assertEqual(quantity('12.00'), '12')
        self.assertEqual(quantity(None), 'Não informado')


class SyncTests(TestCase):
    def test_publishes_export_as_trips_without_cpf(self):
        snapshot = sync_dailies(year=2026, client=api([ITEM]))
        trip = DailyTrip.objects.get()
        self.assertEqual(trip.commitment, ITEM['numeroEmpenho'])
        self.assertEqual(trip.places, ['rorainopolis'])
        self.assertEqual(snapshot.source_count, 1)
        self.assertNotIn('12345678909', str(snapshot.summary))

    def test_undated_entry_missing_from_export_is_found_by_unit(self):
        official = [*OFFICIAL, {'sigla': 'MPE', 'totalPago': 1009569.48}]
        client = api([ITEM], total=2, units=['101', '25101'], by_unit={'101': [ITEM], '25101': [LUMP]}, official=official)
        snapshot = sync_dailies(year=2026, client=client)
        self.assertEqual(DailyTrip.objects.count(), 1)
        self.assertEqual(snapshot.summary['paid'], '1010649.48')
        self.assertEqual(snapshot.summary['lump_sums'][0]['acronym'], 'MPE')

    def test_incomplete_collection_preserves_previous_snapshot(self):
        DailySnapshot.objects.create(year=2026, summary={'old': True})
        with self.assertRaises(ValueError):
            sync_dailies(year=2026, client=api([ITEM], total=2))
        self.assertEqual(DailySnapshot.objects.get().summary, {'old': True})
        self.assertFalse(DailyTrip.objects.exists())

    def test_divergent_official_total_preserves_previous_snapshot(self):
        DailySnapshot.objects.create(year=2026, summary={'old': True})
        with self.assertRaises(ValueError):
            sync_dailies(year=2026, client=api([ITEM], official=[{'sigla': 'ORG', 'totalPago': 5}]))
        self.assertEqual(DailySnapshot.objects.get().summary, {'old': True})

    def test_repeated_commitment_with_other_data_fails(self):
        with self.assertRaises(ValueError):
            sync_dailies(year=2026, client=api([ITEM, {**ITEM, 'totalPago': 1}], total=2))

    def test_invalid_payload_fails(self):
        with self.assertRaises(ValueError):
            sync_dailies(year=2026, client=api({'content': []}, total=0))

    def test_second_collection_replaces_the_year(self):
        sync_dailies(year=2026, client=api([ITEM]))
        other = {**ITEM, 'numeroEmpenho': '2', 'totalPago': 1080}
        sync_dailies(year=2026, client=api([other]))
        self.assertEqual(list(DailyTrip.objects.values_list('commitment', flat=True)), ['2'])


class PageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        second = {**ITEM, 'numeroEmpenho': '2', 'localidade': 'Lisboa/Portugal', 'totalPago': 0, 'totalEstornado': 500}
        sync_dailies(year=2026, client=api([ITEM, second]))
        cls.person = DailyTrip.objects.first().person_id

    def test_empty_state_does_not_deny_payments(self):
        DailySnapshot.objects.all().delete()
        response = self.client.get('/diarias/')
        self.assertContains(response, 'Isso não significa que não houve pagamentos')

    def test_pages_are_served_without_external_api(self):
        with patch('integrations.fiplan_api.client.FiplanClient', side_effect=AssertionError('external call')):
            for url in ('/diarias/', '/diarias/viagens/', '/diarias/pessoas/', f'/diarias/2026/{self.person}/'):
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_cpf_is_never_rendered(self):
        for url in ('/diarias/', '/diarias/viagens/', '/diarias/pessoas/', f'/diarias/2026/{self.person}/'):
            content = self.client.get(url).content.decode()
            self.assertNotIn('123.456.789-09', content)
            self.assertNotIn('12345678909', content)

    def test_trip_cards_name_the_recorded_creditor(self):
        response = self.client.get('/diarias/viagens/', {'ano': 2026, 'lugar': 'rorainopolis'})
        self.assertContains(response, 'Credor informado pela fonte')
        self.assertContains(response, 'Pessoa de teste')
        home = self.client.get('/diarias/')
        self.assertContains(home, 'Credor informado pela fonte')
        self.assertContains(home, '<dt>Credor</dt><dd>Pessoa de teste</dd>', html=True)
        self.assertContains(self.client.get('/diarias/pessoas/'), 'Pessoa de teste')

    def test_personal_file_asks_search_engines_not_to_index(self):
        response = self.client.get(f'/diarias/2026/{self.person}/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex')
        self.assertContains(response, 'Rorainópolis/RR')

    def test_place_search_ignores_accents(self):
        for query in ('rorainopolis', 'RORAINÓPOLIS'):
            self.assertContains(self.client.get('/diarias/', {'busca': query}), 'data-daily-place="rorainopolis"')

    def test_place_search_without_result_explains_itself(self):
        self.assertContains(self.client.get('/diarias/', {'busca': 'atlantida'}), 'Não encontramos esse lugar')

    def test_selected_place_works_without_javascript(self):
        response = self.client.get('/diarias/', {'lugar': 'portugal'})
        self.assertContains(response, 'Exterior')
        self.assertContains(response, '<h3 class="daily-panel__title">Portugal</h3>', html=True)

    def test_map_links_every_municipality_and_marks_selection(self):
        response = self.client.get('/diarias/')
        self.assertContains(response, 'data-daily-place="uiramuta"')
        self.assertContains(response, 'is-selected')

    def test_every_municipality_has_a_visible_name_on_the_map(self):
        shapes = map_shapes([], 2026, {'slug': 'boa-vista'}, lambda value: 1)
        content = render_to_string('diarias/_map.html', {'shapes': shapes})
        self.assertNotIn('daily-map__label--hidden', content)
        self.assertEqual(content.count('data-daily-label='), 15)
        self.assertIn('daily-map__label--0 is-selected" data-daily-label="boa-vista"', content)
        self.assertLess(content.rindex('</a>'), content.index('<text'))

    def test_panel_shows_one_example_of_the_place(self):
        response = self.client.get('/diarias/')
        self.assertContains(response, 'Uma viagem de exemplo', count=1)
        self.assertContains(response, 'class="daily-example"', count=1)

    def test_snapshot_without_example_still_opens(self):
        snapshot = DailySnapshot.objects.get()
        del snapshot.summary['places'][RORAIMA][0]['example']
        snapshot.save()
        self.assertNotContains(self.client.get('/diarias/'), 'Uma viagem de exemplo')

    def test_invalid_filters_keep_the_page_and_explain(self):
        self.assertContains(self.client.get('/diarias/', {'ano': 'abc'}), 'Selecione um ano válido')
        self.assertContains(self.client.get('/diarias/viagens/', {'tema': 'x'}), 'Selecione um filtro válido')
        self.assertContains(self.client.get('/diarias/pessoas/', {'orgao': 'x'}), 'Selecione um filtro válido')

    def test_trip_filters(self):
        self.assertContains(self.client.get('/diarias/viagens/', {'lugar': 'portugal'}), 'Viagens para Portugal')
        response = self.client.get('/diarias/viagens/', {'lugar': 'portugal'})
        self.assertContains(response, 'Estornado')
        self.assertEqual(len(response.context['tickets']), 1)

    def test_unknown_person_is_not_found(self):
        self.assertEqual(self.client.get('/diarias/2026/inexistente/').status_code, 404)

    def test_trip_without_dates_says_so(self):
        DailyTrip.objects.update(start=None, end=None)
        self.assertContains(self.client.get('/diarias/viagens/'), 'Datas não informadas')

    def test_date_label_for_same_day_trip(self):
        DailyTrip.objects.update(start=date(2026, 1, 2), end=date(2026, 1, 2))
        self.assertContains(self.client.get('/diarias/viagens/'), '02/01/2026')
