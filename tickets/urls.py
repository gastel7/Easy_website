from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    path('reserver/<int:event_id>/', views.reserver_billet, name='reserver'),
]