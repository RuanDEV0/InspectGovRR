from django.urls import path

from . import views

app_name = 'diarias'
urlpatterns = [
    path('', views.index, name='index'),
    path('viagens/', views.trips, name='trips'),
    path('pessoas/', views.people, name='people'),
    path('<int:year>/<str:person_id>/', views.detail, name='detail'),
]
