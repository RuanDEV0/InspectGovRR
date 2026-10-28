from django.urls import path

from . import views

app_name = 'receita_arrecadada'

urlpatterns = [
    path('', views.index, name='index'),
]
