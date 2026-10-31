from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from receita_arrecadada.models import RevenueSnapshot

from .formatting import brl, brl_compact, month_range
from .modules import AVAILABLE


class FormattingTests(SimpleTestCase):
    def test_currency_uses_brazilian_separators(self):
        self.assertEqual(brl('1400000.5'), 'R$ 1.400.000,50')
        self.assertEqual(brl(None), 'Não informado')

    def test_compact_currency_reads_like_speech(self):
        self.assertEqual(brl_compact(Decimal('11980329920.70')), 'R$ 11,98 bilhões')
        self.assertEqual(brl_compact('1266751775.39'), 'R$ 1,27 bilhão')
        self.assertEqual(brl_compact('1400000'), 'R$ 1,4 milhão')
        self.assertEqual(brl_compact('199287.24'), 'R$ 199,29 mil')
        self.assertEqual(brl_compact('950'), 'R$ 950,00')

    def test_month_range(self):
        self.assertEqual(month_range(2026, 1, 10), 'Janeiro a Outubro de 2026')
        self.assertEqual(month_range(2026, 8, 8), 'Agosto de 2026')


class PortalPagesTests(TestCase):
    def test_health_check_confirms_database_connection(self):
        response = self.client.get(reverse('healthz'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_health_check_reports_database_failure(self):
        with patch('portal.views.connection.cursor', side_effect=OSError('database unavailable')):
            response = self.client.get(reverse('healthz'))
        self.assertEqual(response.status_code, 503)

    def test_home_lists_available_and_upcoming_themes(self):
        response = self.client.get(reverse('home'))
        for module in AVAILABLE:
            self.assertContains(response, module.title)
            self.assertContains(response, reverse(module.url_name))
        self.assertContains(response, 'Em preparação')
        self.assertContains(response, 'Restos a pagar')
        self.assertNotContains(response, '/integrations/')

    def test_home_highlights_come_from_imported_data(self):
        self.assertNotContains(self.client.get(reverse('home')), 'Números em destaque')
        RevenueSnapshot.objects.create(
            fiscal_year=2026, month_start=1, month_end=10,
            rows=[{'unit_code': '1', 'unit_name': 'Tesouro do Estado', 'amount': '11980329920.70'}],
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Números em destaque')
        self.assertContains(response, 'R$ 11,98 bilhões')

    def test_every_page_shows_data_source_notice_and_favicon(self):
        for url in (reverse('home'), reverse('glossary'), reverse('unidades:list')):
            response = self.client.get(url)
            self.assertContains(response, 'data-source-dialog')
            self.assertContains(response, 'swagger-ui')
            self.assertContains(response, 'favicon.ico')
            self.assertNotContains(response, 'logo-republica')
            self.assertNotContains(response, 'sem alterações')

    @override_settings(DEBUG=False)
    def test_unknown_page_has_plain_language_and_reference_code(self):
        response = self.client.get('/pagina-que-nao-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Não encontramos esta página ou registro.', status_code=404)
        self.assertContains(response, 'NAVEGACAO-404', status_code=404)
        self.assertContains(response, reverse('home'), status_code=404)

    @override_settings(DEBUG=False)
    def test_unexpected_error_hides_exception_details(self):
        self.client.raise_request_exception = False
        with patch('portal.views._highlights', side_effect=RuntimeError('segredo-teste')):
            response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Não foi possível abrir esta página agora.', status_code=500)
        self.assertContains(response, 'SISTEMA-500', status_code=500)
        self.assertNotContains(response, 'segredo-teste', status_code=500)

    def test_module_pages_show_official_term(self):
        response = self.client.get(reverse('unidades:list'))
        self.assertContains(response, 'Nome oficial: <strong>Unidades orçamentárias</strong>', html=False)
        self.assertContains(response, 'aria-current="page"')
