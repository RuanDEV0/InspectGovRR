from django.urls import path

from . import views

app_name = 'integrations'

urlpatterns = [
    path('get-token', views.get_token, name='get_token'),
    path("get-units", views.get_units, name='get_units'),
    path("get-dailies", views.get_dailies, name='get_dailies'),
    path("get-exec-orcament", views.get_exec_orcament, name='get_exec_orcament'),
    path("get-list-credor", views.get_list_credors_by_total_pago, name='get_list_credors_by_total_pago'),
]