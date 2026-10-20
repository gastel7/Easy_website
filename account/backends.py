import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrPhoneBackend(ModelBackend):
    """Allow authentication using username, email or phone number."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        username = str(username).strip()
        if not username:
            return None

        user_model = get_user_model()
        normalized_phone = self._normalize_phone(username)

        query = Q(username__iexact=username) | Q(email__iexact=username)
        if normalized_phone:
            query |= Q(tel__iexact=normalized_phone)

        try:
            user = user_model._default_manager.get(query)
        except user_model.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    @staticmethod
    def _normalize_phone(value):
        clean = re.sub(r"\s+", "", value).strip()
        if not clean:
            return ""

        if clean.startswith('+'):
            digits = re.sub(r"\D", "", clean[1:])
            return f"+{digits}" if digits else ""

        digits = re.sub(r"\D", "", clean)
        return digits if digits else ""
