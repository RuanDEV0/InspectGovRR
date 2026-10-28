from decimal import Decimal

from django.test import SimpleTestCase, TestCase
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
    def test_home_lists_available_and_upcoming_themes(self):
        response = self.client.get(reverse('home'))
        for module in AVAILABLE:
            self.assertContains(response, module.title)
            self.assertContains(response, reverse(module.url_name))
        self.assertContains(response, 'Em preparação')
        self.assertContains(response, 'Restos a pagar')

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

    def test_module_pages_show_official_term(self):
        response = self.client.get(reverse('unidades:list'))
        self.assertContains(response, 'Nome oficial: <strong>Unidades orçamentárias</strong>', html=False)
        self.assertContains(response, 'aria-current="page"')
