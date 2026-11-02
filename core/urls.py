from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views


app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'), 
    path('a-propos/', views.a_propos, name='a-propos'), 
    path('contact/', views.contact, name='contact'), 
    path('faq/', views.faq, name='faq'), 

    # Les liens d'informations 
    path('centre_aide/', views.centre_aide, name='centre_aide'), 
    path('mentions_legales/', views.mentions_legales, name='mentions_legales'), 
    path('politique_confidentialite/', views.politique_confidentialite, name='politique_confidentialite'), 
    path('conditions_utilisation/', views.conditions_utilisation, name='conditions_utilisation'), 

    # Les vues des évenements
    path('nouvel-evenement/', views.add_event, name='add-event'), 
    path('liste-evenements/', views.events_list, name='events-list'), 
    path('edition/evenement/<int:event_id>/', views.edit_event, name='edit-event'), 
    path('annulation/<int:event_id>/', views.annuler_evenement, name='annuler-evenement'),
    path('suppression/<int:event_id>/', views.delete_event, name='delete-event'), 
    path('detail-evenement/<int:event_id>/', views.detail_event , name='detail-event'), 
    path('favoris/<int:event_id>/', views.toggle_favori, name='toggle-favori')
]




if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

