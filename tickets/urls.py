from django.urls import path

from . import views

app_name = 'tickets'

urlpatterns = [
    path('reserver/<int:event_id>/', views.reserver_billet, name='reserver'),
    path('billet/<int:billet_id>/qr-code/', views.qr_code, name='qr-code'),
    path('verifier/<str:code_unique>/', views.verifier_billet, name='verifier'),
]
