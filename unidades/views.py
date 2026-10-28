from django.shortcuts import render

from portal.glossary import terms

from .kinds import group_units
from .models import Unit


def list_units(request):
    units = Unit.objects.order_by('name')
    return render(request, 'unidades/index.html', {
        'groups': group_units(units),
        'total': len(units),
        'glossary': terms('unidade', 'fundo', 'tesouro'),
    })
