"""Identity: one ``User`` table for clients, freelancers and administrators."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel, UUIDModel

# Handles appear in public profile URLs and in @mentions, so they are limited
# to URL-safe characters — but dots are allowed, because "arif.khan" is how
# people actually write their own handle.
USERNAME_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9](?:[a-z0-9._-]{1,48}[a-z0-9])$",
    message=(
        "Usernames are 3–50 characters: lowercase letters, numbers, dots, "
        "underscores or hyphens, starting and ending with a letter or number."
    ),
)


class Role(models.TextChoices):
    CLIENT = "CLIENT", "Client"
    FREELANCER = "FREELANCER", "Freelancer"
    ADMIN = "ADMIN", "Admin"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, username, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        username = (username or email.split("@")[0]).lower()
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"], validate_unique=False)
        user.save(using=self._db)
        return user

    def create_user(self, email, username=None, password=None, **extra):
        extra.setdefault("role", Role.CLIENT)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, username, password, **extra)

    def create_superuser(self, email, username=None, password=None, **extra):
        extra.update(
            role=Role.ADMIN,
            is_staff=True,
            is_superuser=True,
            is_active=True,
            is_email_verified=True,
            email_verified_at=timezone.now(),
        )
        return self._create(email, username, password, **extra)

    def clients(self):
        return self.filter(role=Role.CLIENT)

    def freelancers(self):
        return self.filter(role=Role.FREELANCER)

    def verified(self):
        return self.filter(
            is_active=True, is_email_verified=True, status=User.Status.ACTIVE
        )


class User(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        BANNED = "BANNED", "Banned"
        CLOSED = "CLOSED", "Closed"

    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(
        max_length=50, unique=True, db_index=True, validators=[USERNAME_VALIDATOR]
    )
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=12, choices=Role.choices, db_index=True)

    # A registration is real but not yet trusted: protected business actions
    # stay blocked until the address is proven.
    is_email_verified = models.BooleanField(default=False, db_index=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    suspension_reason = models.TextField(blank=True)
    suspended_until = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ("-date_joined",)
        indexes = [
            models.Index(fields=["role", "status"]),
            models.Index(fields=["-date_joined"]),
        ]

    def __str__(self) -> str:
        return self.email

    # -- identity ----------------------------------------------------------- #
    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name or self.username

    @property
    def initials(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts[:2]).upper()
        return self.username[:2].upper()

    def get_absolute_url(self) -> str:
        if self.is_freelancer:
            return reverse("directory:freelancer_public", args=[self.username])
        return reverse("clients:client_public", args=[self.username])

    # -- roles -------------------------------------------------------------- #
    @property
    def is_client(self) -> bool:
        return self.role == Role.CLIENT

    @property
    def is_freelancer(self) -> bool:
        return self.role == Role.FREELANCER

    @property
    def is_platform_admin(self) -> bool:
        return self.role == Role.ADMIN or self.is_superuser

    # -- trust -------------------------------------------------------------- #
    @property
    def is_usable(self) -> bool:
        """Can this account sign in at all?"""
        if not self.is_active or self.status in {
            self.Status.BANNED,
            self.Status.CLOSED,
        }:
            return False
        if self.status == self.Status.SUSPENDED:
            if self.suspended_until and self.suspended_until <= timezone.now():
                return True  # the suspension has lapsed
            return False
        return True

    @property
    def can_transact(self) -> bool:
        """Protected business actions need an active, verified account."""
        return self.is_usable and self.is_email_verified

    @property
    def dashboard_url(self) -> str:
        if self.is_platform_admin:
            return "/admin/"
        if self.is_freelancer:
            return reverse("profiles:freelancer_dashboard")
        return reverse("profiles:client_dashboard")


def _token() -> str:
    return secrets.token_urlsafe(32)


def _otp_code() -> str:
    import secrets

    return f"{secrets.randbelow(900000) + 100000}"


class EmailVerificationToken(TimeStampedModel):
    """Single-use proof that the address on an account is reachable.

    The link is printed to the console by Django's console email backend, so
    the flow works locally with no mail server.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_tokens",
    )
    email = models.EmailField()
    token = models.CharField(max_length=80, unique=True, default=_token, editable=False)
    code = models.CharField(max_length=6, default=_otp_code, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"verification<{self.email}>"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
