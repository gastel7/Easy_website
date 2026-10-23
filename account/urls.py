from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views, espace



app_name = 'account'

urlpatterns = [
    path('login/', views.login_view, name='login'), 
    path('logout/', views.logout_view, name='logout'),
    path('logup/', views.logup_view, name='logup'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),


    path('espace/', espace.tableau_de_bord, name='espace'),
    path('espace/mode/', espace.changer_mode, name='espace-mode'),
    path('espace/billets/', espace.mes_billets, name='mes-billets'),
    path('espace/favoris/', espace.mes_favoris, name='favoris'),
    path('espace/evenements/', espace.mes_evenements, name='mes-evenements'),
    path('espace/ventes/', espace.ventes, name='ventes'),
    
    # path('profile/delete/', views.delete_account_view_view, name='delete_account'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)