from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from .fiplan_api.client import FiplanAPI

def get_token(request):
    token = FiplanAPI().get_token()
    return HttpResponse(token)

def get_units(request):
    units = FiplanAPI().get_units()
    return HttpResponse(units)