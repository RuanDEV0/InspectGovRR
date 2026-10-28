from django.test import SimpleTestCase, TestCase

from .kinds import classify
from .models import Unit


class UnitPagesTests(TestCase):
    def test_units_page_reads_existing_records_in_name_order(self):
        Unit.objects.create(code='2', name='Zeta', acronym='Z')
        Unit.objects.create(code='1', name='Alfa', acronym='A')

        response = self.client.get('/unidades/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/css/global.css')
        self.assertContains(response, '/static/unidades/unit.css')
        self.assertContains(response, 'Alfa')
        self.assertContains(response, 'Zeta')
        self.assertLess(response.content.index(b'Alfa'), response.content.index(b'Zeta'))

    def test_units_are_grouped_by_kind_without_internal_code(self):
        Unit.objects.create(code='19104', name='Secretaria de Estado da Saúde', acronym='SESAU')
        Unit.objects.create(code='19105', name=' Fundo Estadual de Saúde', acronym=',FUNSESAU ')

        response = self.client.get('/unidades/')

        self.assertContains(response, 'Secretarias e órgãos do governo')
        self.assertContains(response, 'FUNSESAU')
        self.assertNotContains(response, ',FUNSESAU')
        self.assertNotContains(response, '19104')


class UnitKindTests(SimpleTestCase):
    def test_funds_win_over_the_body_they_mention(self):
        self.assertEqual(classify('Fundo Especial do Ministério Público do Estado de Roraima'), 'fundos')
        self.assertEqual(classify('Ministério Público do Estado de Roraima'), 'poderes')
        self.assertEqual(classify('Secretaria de Estado da Segurança Pública'), 'secretarias')
        self.assertEqual(classify('Polícia Militar do Estado de Roraima'), 'seguranca')
        self.assertEqual(classify('Nome desconhecido'), 'outros')
