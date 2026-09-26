"""Request-scoped plumbing."""

from __future__ import annotations

import threading

from django.utils import timezone

_local = threading.local()


def current_actor():
    """The authenticated user handling the current request, if any.

    Used by ``apps.audit`` so a service that is three layers deep can
    attribute an audit row without every signature having to pass ``actor``
    down.  Explicit ``actor=`` arguments always win over this fallback.
    """
    return getattr(_local, "actor", None)


def current_ip() -> str:
    return getattr(_local, "ip", "") or ""


def current_user_agent() -> str:
    return getattr(_local, "user_agent", "") or ""


def set_actor(user=None, ip: str = "", user_agent: str = ""):
    _local.actor = user
    _local.ip = ip
    _local.user_agent = user_agent


def clear_actor():
    for attr in ("actor", "ip", "user_agent"):
        if hasattr(_local, attr):
            delattr(_local, attr)


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class RequestActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        set_actor(
            user=user if (user and user.is_authenticated) else None,
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
        )
        try:
            return self.get_response(request)
        finally:
            clear_actor()


class DomainErrorMiddleware:
    """Turn a ``DomainError`` raised in any view into its proper response.

    The ``handle_domain_errors`` decorator does this for views that opt in, but
    a service call in an un-decorated view would otherwise surface a
    ``PermissionDenied`` as a 500 — telling the user the server broke when in
    fact they were correctly refused. This is the backstop.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from apps.core.exceptions import DomainError, ValidationFailed
        from apps.core.views import _respond

        if isinstance(exception, DjangoValidationError):
            exception = ValidationFailed("; ".join(exception.messages))
        if not isinstance(exception, DomainError):
            return None
        return _respond(request, exception)
