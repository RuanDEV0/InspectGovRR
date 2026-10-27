from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'integrations'

urlpatterns = [
    path('get-units', RedirectView.as_view(pattern_name='unidades:list', permanent=True), name='get_units'),
    path("get-list-credor", views.get_list_credors_by_total_pago, name='get_list_credors_by_total_pago'),
]
