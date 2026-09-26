"""Template context available on every page."""

from __future__ import annotations

from django.conf import settings


def site(request):
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated)
    if not signed_in:
        role = "guest"
    elif user.is_platform_admin:
        role = "admin"
    elif user.is_freelancer:
        role = "freelancer"
    else:
        role = "client"

    return {
        "SKILLCOIN": settings.SKILLCOIN,
        "BUSINESS_RULES": settings.BUSINESS_RULES,
        "PAYMENT_CHANNELS": settings.PAYMENT_CHANNELS,
        "AI_ENABLED": settings.AI["ENABLED"],
        "nav_role": role,
        "needs_email_verification": signed_in and not user.is_email_verified,
    }
