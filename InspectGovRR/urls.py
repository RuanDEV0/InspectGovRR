"""Rotas do portal; integrations funciona apenas como cliente e coletor."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('portal.urls')),
    path('unidades/', include('unidades.urls')),
    path('receita-arrecadada/', include('receita_arrecadada.urls')),
    path('remuneracoes/', include('remuneracoes.urls')),
    path('diarias/', include('diarias.urls')),
    path('contratos/', include('contratos.urls')),
]

handler404 = 'portal.views.page_not_found'
handler500 = 'portal.views.server_error'
