from django.urls import path

from . import views

app_name = 'remuneracoes'
urlpatterns = [
    path('', views.index, name='index'),
    path('<int:year>/<int:month>/<uuid:record_id>/', views.detail, name='detail'),
]
