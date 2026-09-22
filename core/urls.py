from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.index, name='index'), 
    path('a-propos/', views.a_propos, name='a-propos'), 
]

