from django.test import TestCase

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
