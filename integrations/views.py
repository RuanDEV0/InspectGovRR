from django.http import HttpResponse
from django.shortcuts import render

from .services.unit_service import UnitService
from .services.daily_service import DailyService
from .fiplan_api.client import get_token as getToken,  get_units as getUnits
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