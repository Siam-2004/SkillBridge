"""Wallet balance chip for the signed-in header."""

from __future__ import annotations


def wallet(request):
    """Skipped for signed-out visitors and for administrators, who have no
    spendable wallet of their own to show."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated) or user.is_platform_admin:
        return {"wallet": None}

    from apps.wallets.selectors import get_wallet

    return {"wallet": get_wallet(user)}
