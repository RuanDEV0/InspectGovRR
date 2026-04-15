from django.http import HttpResponse
from django.shortcuts import render

from .services.unit_service import UnitService
from .services.daily_service import DailyService
from .services.credor_service import get_list_credors_by_total_pago as getListCredorsByTotalPago
from .fiplan_api.client import get_token as getToken,  get_units as getUnits, get_exec_orcamen_last_teen_years
import asyncio

unitService = UnitService()
dailyService = DailyService()
def get_token(request):
    token = asyncio.run(getToken())
    return HttpResponse(token)

def get_units(request):
    asyncio.run(getToken())
    units = asyncio.run(getUnits())
    return render(request, 'pages/unit/index.html', {'units': units})

def get_dailies(request):
    #ACHAR UMA MANEIRA DE FORÇAR O GET TOKEN AUTOMATICAMENTE QUANDO SUBIR O SERVER E 24 HORAS DEPOIS.
    asyncio.run(getToken())
    dailyService.save()
    daily = dailyService.get_dailies()
    return HttpResponse(daily)

def get_list_credors_by_total_pago(request):
    asyncio.run(getToken())
    units = getListCredorsByTotalPago()
    return HttpResponse(units)