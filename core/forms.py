from django import forms

from .models import Events


class EventForm(forms.ModelForm):
    class Meta:
        model = Events
        fields = [
            'titre', 'categorie', 'lieu', 'adresse', 'ville', 'pays', 'date_debut', 'date_fin', 'statut', 'nombre_de_places',
            'age_minimum', 'description', 'image_principale', 'image_2', 'image_3', 'image_4', 'image_5', 'video'
        ]

        widgets = {
            'titre': forms.TextInput(attrs={'placeholder': "Ex : Conférence sur l'intelligence artificielle"}),
            'lieu': forms.TextInput(attrs={'placeholder': 'Ex : Centre de conférence de Brazzaville'}),
            'adresse': forms.TextInput(attrs={'placeholder': 'Ex : Quartier ou le numéro et nom de la rue'}),
            'ville': forms.TextInput(attrs={'placeholder': 'Ex : Brazzaville'}),
            'pays': forms.TextInput(attrs={'placeholder': 'Ex : République du Congo'}),
            'nombre_de_places': forms.NumberInput(attrs={'placeholder': 'Ex : 150'}),
            'age_minimum': forms.NumberInput(attrs={'placeholder': 'Ex : 18'}),
            'description': forms.Textarea(attrs={'placeholder': "Décrivez l'événement, les thèmes abordés, les objectifs, etc."}),
            'date_debut': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'date_fin': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }