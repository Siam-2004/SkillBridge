"""Reusable field validators ( server-side validation, file safety)."""

from __future__ import annotations

import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

# Extensions that can execute in a browser or on a server if ever served
# directly.  Even though private files are streamed through a permission check,
# we refuse them at the door.
DANGEROUS_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".bat",
    ".cmd",
    ".com",
    ".msi",
    ".app",
    ".scr",
    ".jar",
    ".php",
    ".phtml",
    ".asp",
    ".aspx",
    ".jsp",
    ".cgi",
    ".htaccess",
    ".pl",
    ".vbs",
    ".ps1",
    ".apk",
    ".deb",
    ".rpm",
    ".dmg",
}


def as_domain_error(validator, value, field: str = ""):
    """Run a field validator from inside a service.

    Validators raise Django's ``ValidationError`` because forms collect it into
    field errors. Services promise ``DomainError`` instead, so the two contracts
    meet here rather than leaking a 500 out of a view.
    """
    from apps.core.exceptions import ValidationFailed

    try:
        return validator(value)
    except ValidationError as exc:
        raise ValidationFailed(
            "; ".join(exc.messages),
            errors={field: exc.messages} if field else {},
        ) from exc


URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
PHONE_RE = re.compile(r"^(?:\+?88)?01[3-9]\d{8}$")
MOBILE_ACCOUNT_RE = re.compile(r"^01[3-9]\d{8}$")
TXN_ID_RE = re.compile(r"^[A-Za-z0-9\-_]{6,40}$")


def validate_upload(uploaded_file):
    """Size + extension gate applied to every FileField in the project."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if not ext:
        raise ValidationError("Files must have an extension.")
    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError(f"{ext} files are not allowed.")
    allowed = {
        f".{e.strip().lower().lstrip('.')}" for e in settings.ALLOWED_UPLOAD_EXTENSIONS
    }
    if ext not in allowed:
        raise ValidationError(
            f"{ext} files are not supported. Allowed: {', '.join(sorted(allowed))}"
        )
    max_mb = settings.BUSINESS_RULES["MAX_UPLOAD_MB"]
    if uploaded_file.size > max_mb * 1024 * 1024:
        raise ValidationError(
            f"File is {filesizeformat(uploaded_file.size)}; the limit is {max_mb} MB."
        )
    return uploaded_file


def validate_image(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        raise ValidationError("Upload a PNG, JPG, GIF or WebP image.")
    if uploaded_file.size > 8 * 1024 * 1024:
        raise ValidationError("Images must be 8 MB or smaller.")
    return uploaded_file


def validate_url(value):
    if value and not URL_RE.match(value):
        raise ValidationError("Enter a full URL starting with http:// or https://")
    return value


def validate_bd_phone(value):
    if value and not PHONE_RE.match(value.replace(" ", "").replace("-", "")):
        raise ValidationError(
            "Enter a valid Bangladeshi mobile number, e.g. 01712345678."
        )
    return value


def validate_mobile_account(value):
    """bKash / Nagad account numbers."""
    cleaned = (value or "").replace(" ", "").replace("-", "")
    if not MOBILE_ACCOUNT_RE.match(cleaned):
        raise ValidationError("Enter an 11-digit bKash/Nagad number, e.g. 01712345678.")
    return cleaned


def validate_external_txn_id(value):
    """/the operator types this off their bKash statement."""
    cleaned = (value or "").strip().upper()
    if not TXN_ID_RE.match(cleaned):
        raise ValidationError(
            "Transaction IDs are 6–40 letters, digits, hyphens or underscores."
        )
    return cleaned


def validate_future_datetime(value):
    from django.utils import timezone

    if value and value <= timezone.now():
        raise ValidationError("Choose a date and time in the future.")
    return value
