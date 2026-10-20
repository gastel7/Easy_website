# Pour la gestion des numéros de téléphones et code indicatif du pays
import phonenumbers 
from django_countries.widgets import CountrySelectWidget
from django_countries.fields import CountryField

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _


User = get_user_model() 


class EmailOrPhoneAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label=_('Email ou téléphone'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com ou +33612345678',
            'autocomplete': 'username',
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'id': 'id_username',
            'name': 'username',
        })

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    _('Veuillez saisir un email ou un numéro de téléphone valide et un mot de passe correct.'),
                    code='invalid_login',
                )
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


# Formulaire de création de compte utilisateur
class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['role', 'email', 'first_name', 'last_name', 'tel', 'password1', 'password2']

        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Jean'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dupont'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'tel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '06 00 00 00 00'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm peut ajouter 'username' tout seul : on l'enlève
        self.fields.pop('username', None)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cet email."))
        return email

    def clean_tel(self):
        # Combine l'indicatif choisi dans le <select name="country_code"> avec le numéro
        tel = (self.cleaned_data.get('tel') or '').replace(' ', '')
        code = self.data.get('country_code', '')
        if tel and not tel.startswith('+'):
            tel = code + tel.lstrip('0')
        return tel

    def save(self, commit=True):
        user = super().save(commit=False)

        # Génération d'un username unique à partir de l'email
        base = self.cleaned_data['email'].split('@')[0]
        username = base
        i = 1
        while User.objects.filter(username=username).exists():
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
        fields = ['role', 'username', 'email',  'first_name', 'last_name','tel', 'civilite', 'nationalite']

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'tel': forms.TextInput(attrs={'class': 'form-control'}),
            'civilite': forms.Select(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'nationalite': forms.TextInput(attrs={'class': 'form-control'}),
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