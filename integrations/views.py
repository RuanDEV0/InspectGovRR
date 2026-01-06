from django.http import HttpResponse
from .services.unit_service import UnitService
from .fiplan_api.client import FiplanAPI

unitService = UnitService()
def get_token(request):
    token = FiplanAPI().get_token()
    return HttpResponse(token)

def get_units(request):
    units = unitService.get_units()
    return HttpResponse(units)