"""Registration, email verification, sign-in throttling and moderation."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, Role, User
from apps.core.exceptions import (
    DomainError,
    InvalidState,
    PermissionDenied,
    ValidationFailed,
)
from apps.core.permissions import require_admin


class RateLimited(DomainError):
    status_code = 429
    default_message = "Too many attempts. Please wait and try again."


# (attempts, seconds) — plain fixed windows, held in Django's default
# local-memory cache. No external store is involved.
RATE_LIMITS = {
    "login": (10, 300),
    "register": (5, 3600),
    "verify_resend": (5, 3600),
}


def _throttle(key: str, limit: int, window: int) -> None:
    """Fixed-window counter in the local cache.

    Fails *open* if the cache misbehaves: a throttling bug must not lock every
    user out of signing in, and the password hasher still gates access.
    """
    try:
        cache.get_or_set(key, 0, window)  # create the window if absent
        count = cache.incr(key)
    except Exception:
        return
    if count > limit:
        raise RateLimited(
            f"Too many attempts. Try again in {max(window // 60, 1)} minute(s)."
        )


def _unique_username(base: str) -> str:
    """Derive a free, validator-safe handle from a name or email local part."""
    import re

    candidate = re.sub(r"[^a-z0-9._-]+", "-", (base or "").lower()).strip("._-")[:40]
    candidate = re.sub(r"[-._]{2,}", "-", candidate)
    if len(candidate) < 3:
        candidate = f"user-{candidate}" if candidate else "user"
    if not User.objects.filter(username=candidate).exists():
        return candidate
    for suffix in range(1, 200):
        probe = f"{candidate}{suffix}"[:50]
        if not User.objects.filter(username=probe).exists():
            return probe
    import secrets

    return f"{candidate[:40]}{secrets.token_hex(3)}"


@transaction.atomic()
def register(
    *,
    email: str,
    password: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    ip: str = "",
) -> User:
    """Create an account and send the verification email.

    The account exists immediately but cannot transact until the address is
    verified, which is what ``User.can_transact`` gates.
    """
    email = (email or "").strip().lower()
    if not email:
        raise ValidationFailed("An email address is required.")
    if role not in {Role.CLIENT, Role.FREELANCER}:
        raise ValidationFailed("Choose whether you are hiring or freelancing.")
    if ip:
        limit, window = RATE_LIMITS["register"]
        _throttle(f"rl:register:{ip}", limit, window)

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationFailed(
            "An account with that email already exists. Sign in instead.",
            errors={"email": "Already registered."},
        )

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise ValidationFailed(
            "Choose a stronger password.", errors={"password": list(exc.messages)}
        ) from exc

    try:
        user = User.objects.create_user(
            email=email,
            username=_unique_username(username or email.split("@")[0]),
            password=password,
            role=role,
            first_name=first_name.strip()[:80],
            last_name=last_name.strip()[:80],
        )
    except IntegrityError as exc:
        raise ValidationFailed("That email or username is already taken.") from exc

    send_verification_email(user=user)
    return user


@transaction.atomic()
def send_verification_email(*, user: User) -> EmailVerificationToken:
    """Issue a fresh single-use token, superseding any outstanding one."""
    if user.is_email_verified:
        raise InvalidState("This address is already verified.")

    limit, window = 5, 3600
    _throttle(f"rl:verify:{user.pk}", limit, window)

    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    hours = settings.BUSINESS_RULES["EMAIL_TOKEN_EXPIRY_HOURS"]
    verification = EmailVerificationToken.objects.create(
        user=user,
        email=user.email,
        expires_at=timezone.now() + timedelta(hours=hours),
    )

    def _send():
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
        url = f"{site_url}{reverse('accounts:verify_email', args=[verification.token])}"
        ctx = {
            "user": user,
            "verify_url": url,
            "code": verification.code,
            "hours": hours,
        }
        try:
            html = render_to_string("emails/verify_email.html", ctx)
            text = render_to_string("emails/verify_email.txt", ctx)
            mail = EmailMultiAlternatives(
                subject="[SkillBridge] Verify your email address",
                body=text,
                to=[user.email],
            )
            mail.attach_alternative(html, "text/html")
            mail.send(fail_silently=False)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Verification email sending failed: %s", exc, exc_info=True
            )

    transaction.on_commit(_send)
    return verification


@transaction.atomic()
def verify_email(*, token: str) -> User:
    verification = (
        EmailVerificationToken.objects.select_for_update()
        .select_related("user")
        .filter(token=token)
        .first()
    )
    if verification is None:
        raise ValidationFailed("That verification link is not valid.")
    if verification.used_at is not None:
        if verification.user.is_email_verified:
            return verification.user
        raise ValidationFailed("That link has already been used.")
    if verification.expires_at <= timezone.now():
        raise ValidationFailed(
            "That link has expired. Request a new verification email."
        )

    user = verification.user
    verification.used_at = timezone.now()
    verification.save(update_fields=["used_at", "updated_at"])

    if not user.is_email_verified:
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(
            update_fields=["is_email_verified", "email_verified_at", "updated_at"]
        )
    return user


@transaction.atomic()
def verify_code(*, code: str, user: User | None = None) -> User:
    """Verify an account using the 6-digit OTP code."""
    code = (code or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        raise ValidationFailed("Please enter a valid 6-digit verification code.")

    qs = EmailVerificationToken.objects.select_for_update().select_related("user")
    if user and user.is_authenticated:
        verification = qs.filter(user=user, code=code).first()
    else:
        verification = (
            qs.filter(code=code, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

    if verification is None:
        raise ValidationFailed("The verification code is incorrect.")

    if verification.used_at is not None:
        if verification.user.is_email_verified:
            return verification.user
        raise ValidationFailed("That verification code has already been used.")

    if verification.expires_at <= timezone.now():
        raise ValidationFailed(
            "That verification code has expired. Please request a new one."
        )

    target_user = verification.user
    verification.used_at = timezone.now()
    verification.save(update_fields=["used_at", "updated_at"])

    if not target_user.is_email_verified:
        target_user.is_email_verified = True
        target_user.email_verified_at = timezone.now()
        target_user.save(
            update_fields=["is_email_verified", "email_verified_at", "updated_at"]
        )
    return target_user


def login(*, request, identifier: str, password: str) -> User:
    """Authenticate with throttling and an audit trail."""
    from apps.core.middleware import client_ip

    identifier = (identifier or "").strip().lower()
    ip = client_ip(request)
    limit, window = RATE_LIMITS["login"]
    _throttle(f"rl:login:{ip}:{identifier[:60]}", limit, window)

    user = authenticate(request, username=identifier, password=password)
    if user is None:
        # Distinguish "wrong password" from "account disabled" only for the
        # latter, and only once the password matched, so the message cannot be
        # used to enumerate suspended accounts.
        candidate = User.objects.filter(email__iexact=identifier).first()
        if candidate and candidate.check_password(password) and not candidate.is_usable:
            raise PermissionDenied(
                candidate.suspension_reason
                or "This account is not active. Contact support."
            )
        raise ValidationFailed("Email or password is incorrect.")

    # A lapsed suspension lifts itself on the next successful sign-in.
    if (
        user.status == User.Status.SUSPENDED
        and user.suspended_until
        and (user.suspended_until <= timezone.now())
    ):
        user.status = User.Status.ACTIVE
        user.suspension_reason = ""
        user.suspended_until = None
        user.save(
            update_fields=[
                "status",
                "suspension_reason",
                "suspended_until",
                "updated_at",
            ]
        )

    User.objects.filter(pk=user.pk).update(last_seen_at=timezone.now())
    return user


@transaction.atomic()
def change_password(*, user: User, current_password: str, new_password: str) -> User:
    if not user.check_password(current_password):
        raise ValidationFailed(
            "Your current password is incorrect.",
            errors={"current_password": "Incorrect."},
        )

    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationFailed(
            "Choose a stronger password.", errors={"new_password": list(exc.messages)}
        ) from exc

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    return user


@transaction.atomic()
def suspend_user(
    *, user: User, admin, reason: str, days: int | None = None, ban: bool = False
) -> User:
    """Suspend or ban an account, always audited."""
    require_admin(admin)
    if not reason.strip():
        raise ValidationFailed("A suspension reason is required.")
    if user.pk == admin.pk:
        raise PermissionDenied("You cannot suspend your own account.")
    if user.is_platform_admin and not admin.is_superuser:
        raise PermissionDenied("Only a superuser can suspend an administrator.")

    previous = {"status": user.status, "reason": user.suspension_reason}
    user.status = User.Status.BANNED if ban else User.Status.SUSPENDED
    user.suspension_reason = reason[:1000]
    user.suspended_until = (
        timezone.now() + timedelta(days=days) if days and not ban else None
    )
    user.save(
        update_fields=["status", "suspension_reason", "suspended_until", "updated_at"]
    )
    return user


@transaction.atomic()
def reinstate_user(*, user: User, admin, note: str = "") -> User:
    require_admin(admin)
    previous = {"status": user.status, "reason": user.suspension_reason}
    user.status = User.Status.ACTIVE
    user.suspension_reason = ""
    user.suspended_until = None
    user.save(
        update_fields=["status", "suspension_reason", "suspended_until", "updated_at"]
    )
    return user
