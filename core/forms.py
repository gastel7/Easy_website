from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Events

ROLES_CHOISIR_ORGANISATEUR = ('admin', 'modérateur')


def peut_choisir_organisateur(user):
    """Un admin ou un modérateur peut créer un événement au nom d'un organisateur."""
    return user.is_superuser or getattr(user, 'role', None) in ROLES_CHOISIR_ORGANISATEUR


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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Organisateur simple : pas de champ. La vue met l'utilisateur connecté.
        if user is None or not peut_choisir_organisateur(user):
            return

        User = get_user_model()
        organisateurs = User.objects.filter(role='organisateur')
        if self.instance.pk:
            # En modification, on garde l'organisateur actuel, même si son rôle a changé
            organisateurs = User.objects.filter(Q(role='organisateur') | Q(pk=self.instance.organisateur_id))

        self.fields['organisateur'] = forms.ModelChoiceField(
            queryset=organisateurs.order_by('username'),
            label="Organisateur",
            required=True,
        )

        if self.instance.pk:
            # Modification : affiché avec la valeur actuelle, mais non modifiable
            self.fields['organisateur'].disabled = True
            self.initial['organisateur'] = self.instance.organisateur_id