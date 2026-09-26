from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Sign in with either the email address or the username.

    Suspended/banned accounts are rejected here rather than after login, so a
    disabled account never obtains a session.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        identifier = (username or kwargs.get("email") or "").strip().lower()
        if not identifier or not password:
            return None
        try:
            user = User.objects.get(
                Q(email__iexact=identifier) | Q(username__iexact=identifier)
            )
        except User.DoesNotExist:
            # Equalise timing so a wrong address is indistinguishable from a
            # wrong password.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return bool(user and user.is_usable)
