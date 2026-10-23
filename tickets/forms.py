from django import forms
from django.core.exceptions import ValidationError

from core.models import Events
from .models import TicketCategory

FORMAT_DATETIME_LOCAL = '%Y-%m-%dT%H:%M'


class TicketForm(forms.ModelForm):
    """Un billet. Les règles (prix, quantité, dates) sont dans TicketCategory.clean()."""

    class Meta:
        model = TicketCategory
        fields = ['nom', 'type_de_ticket', 'prix', 'quantite_disponible', 'date_debut_vente', 'date_fin_vente']

        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Ex : Standard, VIP, Early Bird'}),
            'prix': forms.NumberInput(attrs={'placeholder': 'Ex : 10000'}),
            'quantite_disponible': forms.NumberInput(attrs={'placeholder': 'Ex : 200'}),
            'date_debut_vente': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=FORMAT_DATETIME_LOCAL),
            'date_fin_vente': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=FORMAT_DATETIME_LOCAL),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le total des places est vérifié par le formset (voir plus bas), pas billet par billet
        self.instance.verifier_total = False


class BaseTicketFormSet(forms.BaseInlineFormSet):
    # La vue y met le nombre de places envoyé avec le formulaire de l'événement
    places_max = None

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {
            'too_few_forms': "Ajoutez au moins un billet.",
            'too_many_forms': "Vous ne pouvez pas créer plus de 10 billets.",
        })
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()

        # Si un billet a déjà une erreur, on la corrige d'abord
        if any(self.errors):
            return

        erreurs = []
        total = 0

        for form in self.forms:
            # Billet retiré : impossible si des tickets ont déjà été vendus (UserTicket est en PROTECT)
            if self.can_delete and self._should_delete_form(form):
                if form.instance.pk and form.instance.user_tickets.exists():
                    erreurs.append(f"Le billet « {form.instance.nom} » a déjà été vendu : il ne peut pas être retiré.")
                continue

            quantite = form.cleaned_data.get('quantite_disponible')
            if quantite is None:   # ligne vide
                continue

            total += quantite

            # On ne peut pas descendre sous le nombre de billets déjà vendus
            if form.instance.pk:
                vendus = form.instance.user_tickets.exclude(statut='annule').count()
                if quantite < vendus:
                    erreurs.append(f"Le billet « {form.instance.nom} » a déjà {vendus} ticket(s) vendu(s) : la quantité ne peut pas être inférieure.")

        if self.places_max is not None and total > self.places_max:
            erreurs.append(f"Vous avez réparti {total} places dans les billets, mais l'événement n'en compte que {self.places_max}.")

        if erreurs:
            raise ValidationError(erreurs)


TicketFormSet = forms.inlineformset_factory(
    Events,
    TicketCategory,
    form=TicketForm,
    formset=BaseTicketFormSet,
    extra=0,            # pas de ligne en plus : min_num en affiche déjà une
    min_num=1,          # au moins un billet
    validate_min=True,
    max_num=10,
    validate_max=True,
    can_delete=True,
)