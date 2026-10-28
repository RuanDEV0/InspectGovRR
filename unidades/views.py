from django.shortcuts import render

from .models import Unit


def list_units(request):
    units = Unit.objects.order_by('name')
    return render(request, 'unidades/index.html', {'units': units})
