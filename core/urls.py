from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'),
    path('a-propos/', views.a_propos, name='a-propos'),
    path('evenements/', views.event_list, name='event-list'),
    path('evenements/creer/', views.event_create, name='event-create'),
    path('evenements/<slug:slug>/', views.event_detail, name='event-detail'),
    path('evenements/<int:pk>/modifier/', views.event_update, name='event-update'),
    path('evenements/<int:pk>/supprimer/', views.event_delete, name='event-delete'),
]

