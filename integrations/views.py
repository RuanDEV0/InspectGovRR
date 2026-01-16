from django.http import HttpResponse
from .services.unit_service import UnitService
from .services.daily_service import DailyService
from .fiplan_api.client import FiplanAPI

unitService = UnitService()
dailyService = DailyService()

def get_token(request):
    token = FiplanAPI().get_token()
    return HttpResponse(token)

def get_units(request):
    units = unitService.get_units()
    return HttpResponse(units)

def get_dailies(request):
    daily = dailyService.get_dailies()
    return HttpResponse(daily)