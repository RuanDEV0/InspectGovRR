from django.urls import path

from . import views

app_name = 'unidades'

urlpatterns = [
    path('', views.list_units, name='list'),
]
