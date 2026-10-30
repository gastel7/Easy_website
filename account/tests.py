from django.test import TestCase

from .forms import SignUpForm


class SignUpFormTests(TestCase):
    def test_password_can_be_shorter_than_eight_characters(self):
        form = SignUpForm(data={
            'role': 'participant',
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'jean.dupont@example.com',
            'tel': '+33612345678',
            'password1': 'qZ7!',
            'password2': 'qZ7!',
        })

        self.assertTrue(form.is_valid(), form.errors)
