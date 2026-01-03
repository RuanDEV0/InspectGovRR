from django.urls import path

from . import views

urlpatterns = [
    path('get-token', views.get_token, name='get_token'),
    path("get-units", views.get_units, name='get_units'),
]