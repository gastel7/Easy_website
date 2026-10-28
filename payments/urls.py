from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    # Chemins fixes d'abord, avant <str:reference>/
    path('webhook/tamo/', views.webhook_tamo, name='webhook'),
    path('billet/<int:billet_id>/', views.paiement_du_billet, name='billet'),

    path('<str:reference>/', views.page_paiement, name='page'),
    path('<str:reference>/lancer/', views.lancer_collecte, name='lancer'),
    path('<str:reference>/statut/', views.statut_paiement, name='statut'),
    path('<str:reference>/checkout/', views.confirmer_checkout, name='checkout'),
]
