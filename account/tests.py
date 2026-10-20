from django.contrib.auth import get_user_model
from django.test import TestCase

from account.backends import EmailOrPhoneBackend


class EmailOrPhoneAuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            email='alice@example.com',
            tel='+33612345678',
            password='StrongPassword123!',
            first_name='Alice',
            last_name='Martin',
            civilite='Femme',
        )

    def test_authenticate_with_email(self):
        user = EmailOrPhoneBackend().authenticate(None, username='alice@example.com', password='StrongPassword123!')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'alice@example.com')

    def test_authenticate_with_phone(self):
        user = EmailOrPhoneBackend().authenticate(None, username='+33612345678', password='StrongPassword123!')
        self.assertIsNotNone(user)
        self.assertEqual(user.tel, '+33612345678')
