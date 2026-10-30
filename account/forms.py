import re

# Pour la gestion des numéros de téléphones et code indicatif du pays
import phonenumbers 
from django_countries.widgets import CountrySelectWidget
from django_countries.fields import CountryField

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import MinimumLengthValidator, get_default_password_validators, validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .utils import normalize_phone


User = get_user_model() 

# Saisie qui ressemble à un numéro (chiffres, espaces, points, tirets, parenthèses)
PHONE_LIKE = re.compile(r'[\d\s.\-()]+')

# Rôles que l'on peut choisir soi-même à l'inscription.
# (admin et modérateur ne doivent JAMAIS être attribuables depuis un formulaire public)
SIGNUP_ROLES = [c for c in User.ROLE_CHOICES if c[0] in ('organisateur', 'participant')]


# Formulaire de connexion : un seul champ "email ou téléphone"
class EmailOrPhoneAuthenticationForm(forms.Form):
    identifier = forms.CharField(label=_('Email ou téléphone'))
    password = forms.CharField(strip=False, widget=forms.PasswordInput)

    error_messages = {
        'invalid_login': _('Identifiants incorrects. Vérifiez votre email ou numéro de téléphone et votre mot de passe.'),
        'invalid_phone': _("Numéro de téléphone invalide. Saisissez-le avec l'indicatif du pays, par exemple +242 06 123 4567."),
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        identifier = (cleaned.get('identifier') or '').strip()
        password = cleaned.get('password')
        if not identifier or not password:
            return cleaned  # les erreurs "champ obligatoire" sont déjà levées

        # Message précis si ça ressemble à un numéro mais qu'il est mal saisi
        # (sans indicatif, ou invalide). Sinon : email (ou username pour l'admin).
        if '@' not in identifier:
            looks_like_phone = identifier.startswith('+') or PHONE_LIKE.fullmatch(identifier)
            if looks_like_phone and normalize_phone(identifier) is None:
                raise forms.ValidationError(self.error_messages['invalid_phone'], code='invalid_phone')

        self.user_cache = authenticate(self.request, username=identifier, password=password)
        if self.user_cache is None:
            raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')

        return cleaned

    def get_user(self):
        return self.user_cache


# Formulaire de création de compte utilisateur
class SignUpForm(UserCreationForm):
    # Limite les rôles autorisés (sinon n'importe qui peut poster role=admin)
    role = forms.ChoiceField(choices=SIGNUP_ROLES)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['role', 'email', 'first_name', 'last_name', 'tel', 'password1', 'password2']

        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Jean'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dupont'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'tel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+242 06 123 4567'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm peut ajouter 'username' tout seul : on l'enlève
        self.fields.pop('username', None)

        # Email ET téléphone obligatoires : c'est ce qui sert à se connecter
        for name in ('email', 'tel', 'first_name', 'last_name'):
            self.fields[name].required = True

    def validate_password_for_user(self, user, password_field_name="password2"):
        password = self.cleaned_data.get(password_field_name)
        if password:
            validators = [
                validator
                for validator in get_default_password_validators()
                if not isinstance(validator, MinimumLengthValidator)
            ]
            try:
                validate_password(password, user, password_validators=validators)
            except ValidationError as error:
                self.add_error(password_field_name, error)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cet email."))
        return email

    def clean_tel(self):
        # Le numéro doit être saisi avec l'indicatif (+242 ...) ; on le stocke en format international
        phone = normalize_phone(self.cleaned_data.get('tel'))
        if phone is None:
            raise forms.ValidationError(
                _("Numéro invalide. Saisissez-le avec l'indicatif du pays, par exemple +242 06 123 4567.")
            )
        if User.objects.filter(tel=phone).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec ce numéro."))
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)

        # Génération d'un username unique à partir de l'email
        base = self.cleaned_data['email'].split('@')[0]
        username = base
        i = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}{i}"
            i += 1
        user.username = username

        if commit:
            user.save()
        return user


# Formulaire de mise à jour
class UpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['role', 'username', 'email',  'first_name', 'last_name','tel', 'civilite', 'nationalite', 'birth_date', 'adresse', 'profile_picture']

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'tel': forms.TextInput(attrs={'class': 'form-control'}),
            'civilite': forms.Select(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'nationalite': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date' }),
            'adresse': forms.TextInput(attrs={'class': 'form-control',}),
        }


class PhoneForm(forms.Form):
    country = CountryField(blank_label = '(Select Country)').formfield(
        widget = CountrySelectWidget()
    )

    phone_number = forms.CharField(max_length=15, label="Phone number")

    def clean_phone_number(self):

        phone_number = self.cleaned_data.get('phone_number')
        country_code = self.cleaned_data.get('country')

        if country_code:
            full_number = phonenumbers.parse(phone_number, str(country_code))

            if not phonenumbers.is_valid_number(full_number):
                raise forms.ValidationError("Ce numéro n'est pas valide ❌.")

        return phone_number