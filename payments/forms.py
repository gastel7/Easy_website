import re

import phonenumbers
from django import forms

from .models import OPERATEURS


# Région → opérateur disponible chez Tamo (doc TASA : MTN_CG, ORANGE_SN)
OPERATEURS_PAR_REGION = {
    'CG': 'MTN_CG',
    'SN': 'ORANGE_SN',
}

# Pays supposé quand le numéro n'est pas saisi en format international (+242…)
REGION_PAR_DEFAUT = 'CG'  # Congo-Brazzaville


def normaliser_telephone(valeur):
    """Renvoie le numéro en format international (+242061234567) ou None.

    Sans « + » on interprète le numéro comme un numéro local (région par défaut) :
    068409872 → +242068409872. Un « + » explicite reste tel quel.
    """
    brut = re.sub(r'[\s().\-/]', '', (valeur or '').strip())
    if not brut:
        return None
    international = brut.startswith('+')
    try:
        # Sans « + », phonenumbers interprète le numéro comme un numéro local de la région
        numero = phonenumbers.parse(brut, None if international else REGION_PAR_DEFAUT)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(numero):
        return None
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def operateur_du_numero(numero):
    """MTN Congo / Orange Sénégal selon le pays du numéro, '' si inconnu."""
    try:
        parsed = phonenumbers.parse(numero, REGION_PAR_DEFAUT)
        region = phonenumbers.region_code_for_number(parsed) \
            or phonenumbers.region_code_for_country_code(parsed.country_code)
    except phonenumbers.NumberParseException:
        return ''
    return OPERATEURS_PAR_REGION.get(region, '')


class CollecteForm(forms.Form):
    """Numéro Mobile Money à débiter pour la collecte."""

    telephone = forms.CharField(
        label="Numéro Mobile Money",
        max_length=30,
        widget=forms.TextInput(attrs={
            'placeholder': '+242 06 431 17 69',
            'autocomplete': 'tel',
            'inputmode': 'tel',
            'data-telephone': '',
        }),
        error_messages={'required': "Indiquez le numéro qui doit recevoir la demande de paiement."},
    )
    operateur = forms.ChoiceField(
        label="Opérateur",
        required=False,
        choices=[('', 'Selon le numéro')] + OPERATEURS,
        widget=forms.Select(attrs={'data-operateur': ''}),
    )

    def clean_telephone(self):
        numero = normaliser_telephone(self.cleaned_data['telephone'])
        if not numero:
            raise forms.ValidationError(
                "Numéro invalide. Utilisez le format international, ex : +242064311769.")
        return numero 

    def clean(self):
        cleaned = super().clean()
        numero = cleaned.get('telephone')
        operateur = cleaned.get('operateur')
        if numero and not operateur:
            detecte = operateur_du_numero(numero)
            if not detecte:
                self.add_error('operateur',
                               "Impossible de déterminer l'opérateur : choisissez-le.")
            else:
                cleaned['operateur'] = detecte
        return cleaned
