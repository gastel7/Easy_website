from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .utils import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """Authentifie avec l'email, le numéro de téléphone (format international) ou le username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()

        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        if not username or password is None:
            return None

        identifier = str(username).strip()
        if not identifier:
            return None

        user = self._get_user(identifier)

        if user is None:
            # Même coût de calcul qu'un vrai utilisateur : évite de révéler
            # par le temps de réponse si le compte existe ou non.
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def _get_user(self, identifier):
        user_model = get_user_model()

        if "@" in identifier:
            query = Q(email__iexact=identifier) | Q(username__iexact=identifier)
        elif identifier.startswith("+"):
            phone = normalize_phone(identifier)
            if phone is None:
                return None
            query = Q(tel=phone)
        else:
            query = Q(username__iexact=identifier)

        # [:2] + len() : si deux comptes correspondent (cas anormal), on refuse
        # plutôt que de planter avec MultipleObjectsReturned.
        users = list(user_model._default_manager.filter(query)[:2])
        return users[0] if len(users) == 1 else None