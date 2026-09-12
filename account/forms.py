# Pour la gestion des numéros de téléphones et code indicatif du pays
import phonenumbers 
from django_countries.widgets import CountrySelectWidget
from django_countries.fields import CountryField

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model


User = get_user_model() 

# Formulaire de création de compte utilisateur
class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['role', 'username', 'email',  'first_name', 'last_name','tel', 'password1', 'password2']

        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'xyz_123'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Jean'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dupont'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'tel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '06 00 00 00 00'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'M0nMot_dePasse_Sup3rS3cr3t'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'M0nMot_dePasse_Sup3rS3cr3t'}),
        }


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
        country_code = self.cleaned_data.get('country_code')

        if country_code:
            full_number = phonenumbers.parse(phone_number, country_code)

            if not phonenumbers.is_valid_number(full_number):
                raise forms.ValidationError("Ce numéro n'est pas valide ❌.")

        return phone_number


