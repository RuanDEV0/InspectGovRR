from django.urls import path

from . import views

app_name = 'contratos'
urlpatterns = [
    path('', views.index, name='index'),
    path('vencendo/', views.expiring, name='expiring'),
    path('fornecedor/<str:supplier_id>/', views.supplier, name='supplier'),
]
