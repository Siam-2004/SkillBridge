"""Object-level checks for profiles."""

from __future__ import annotations

from apps.core.exceptions import PermissionDenied


def can_edit_profile(user, profile) -> bool:
    return bool(user and user.is_authenticated and profile.user_id == user.pk)


def require_profile_owner(user, profile):
    if not can_edit_profile(user, profile):
        raise PermissionDenied("This is not your profile.")
    return profile
