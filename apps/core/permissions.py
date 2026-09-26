"""Authorisation primitives.

every protected operation to pass *authentication → role
permission → object permission → business validation*.  These helpers are the
role and object layers; the business layer lives in each app's ``services.py``.
They raise rather than return False so a caller cannot forget to check.
"""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect

from apps.accounts.models import Role
from apps.core.exceptions import NotVerified, PermissionDenied


def require_authenticated(user):
    if not (user and user.is_authenticated):
        raise PermissionDenied("Sign in to continue.")
    return user


def require_role(user, *roles: str):
    require_authenticated(user)
    if user.is_superuser and Role.ADMIN in roles:
        return user
    if user.role not in roles:
        raise PermissionDenied(
            f"This action is limited to {', '.join(r.lower() for r in roles)} accounts."
        )
    return user


def require_client(user):
    return require_role(user, Role.CLIENT)


def require_freelancer(user):
    return require_role(user, Role.FREELANCER)


def require_admin(user):
    require_authenticated(user)
    if not user.is_platform_admin:
        raise PermissionDenied("Administrator access required.")
    return user


def require_verified(user):
    """unverified accounts may browse but not transact."""
    require_authenticated(user)
    if not user.is_usable:
        raise PermissionDenied("This account is not active.")
    if not user.is_email_verified:
        raise NotVerified
    return user


def require_verified_client(user):
    require_client(user)
    return require_verified(user)


def require_verified_freelancer(user):
    require_freelancer(user)
    return require_verified(user)


# --------------------------------------------------------------------------- #
# View decorators — translate a DomainError into a redirect + flash message so
# templates never have to branch on permissions.
# --------------------------------------------------------------------------- #
def _guard(check):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not (user and user.is_authenticated):
                return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
            try:
                check(user)
            except NotVerified as exc:
                messages.warning(request, exc.message)
                return redirect("accounts:verify_notice")
            except PermissionDenied as exc:
                messages.error(request, exc.message)
                return redirect(user.dashboard_url)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


client_required = _guard(require_client)
freelancer_required = _guard(require_freelancer)
admin_required = _guard(require_admin)
verified_required = _guard(require_verified)
verified_client_required = _guard(require_verified_client)
verified_freelancer_required = _guard(require_verified_freelancer)
