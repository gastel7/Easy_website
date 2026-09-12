from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    path('login/', views.login_view, name='login'), 
    path('logout/', views.logout_view, name='logout'),
    path('logup/', views.logup_view, name='logup'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    
    # path('profile/delete/', views.delete_account_view_view, name='delete_account'),
]

