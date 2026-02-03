from django.http import HttpResponse
from .services.unit_service import UnitService
from .services.daily_service import DailyService
from .fiplan_api.client import FiplanAPI, get_token as getToken, get_dailies as getDailies
import asyncio

unitService = UnitService()
dailyService = DailyService()
def get_token(request):
    token = asyncio.run(getToken())
    return HttpResponse(token)

def get_units(request):
    units = unitService.get_units()
    return HttpResponse(units)

def get_dailies(request):
    #ACHAR UMA MANEIRA DE FORÇAR O GET TOKEN AUTOMATICAMENTE QUANDO SUBIR O SERVER E 24 HORAS DEPOIS.
    asyncio.run(getToken())
    daily = asyncio.run(getDailies())
    return HttpResponse(daily)