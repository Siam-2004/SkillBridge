"""Registration, sign-in, email verification and account settings.

Password reset is Django's own built-in flow, wired up in ``urls.py`` with our
templates — there is no reason to reimplement it.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.accounts import services
from apps.accounts.forms import (
    AccountSettingsForm,
    ChangePasswordForm,
    LoginForm,
    RegisterForm,
)
from apps.core.exceptions import DomainError
from apps.core.middleware import client_ip
from apps.core.selectors import platform_stats

# Only the switchable preferences appear here; NotificationPreference.ALWAYS_EMAIL
# covers the money, dispute and invitation mails a user may not turn off.
NOTIFICATION_PREF_FIELDS = [
    (
        "email_messages",
        "Messages and mentions",
        "A new message in a job or project conversation, or someone @mentioning you.",
    ),
    (
        "email_proposals",
        "Proposals, offers and counter offers",
        "Activity on jobs you posted, or on proposals you submitted.",
    ),
    (
        "email_tasks",
        "Task activity",
        "Assignments, submitted work, revision requests and approvals.",
    ),
    (
        "email_deadlines",
        "Deadline and review-window reminders",
        "Before a project or task deadline, and before a payment window closes.",
    ),
    (
        "email_marketing",
        "Product news",
        "Occasional updates about new Skillbridge features. Off by default.",
    ),
]


def _safe_next(request) -> str | None:
    """Only follow a same-origin ``next`` so login cannot be used as an open redirect."""
    from django.utils.http import url_has_allowed_host_and_scheme

    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None


@never_cache
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url)

    form = RegisterForm(request.POST or None, initial={"role": request.GET.get("role")})
    if request.method == "POST" and form.is_valid():
        try:
            user = services.register(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                role=form.cleaned_data["role"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                ip=client_ip(request),
            )
        except DomainError as exc:
            messages.error(request, exc.message)
            for field, errors in getattr(exc, "errors", {}).items():
                form.add_error(
                    field if field in form.fields else None,
                    errors if isinstance(errors, str) else "; ".join(errors),
                )
        else:
            django_login(
                request, user, backend="apps.accounts.backends.EmailOrUsernameBackend"
            )
            messages.success(
                request,
                "Account created. Check your inbox to verify your email address — "
                "you will need it before posting jobs or moving SkillCoin.",
            )
            return redirect(reverse("accounts:verify_notice"))

    return render(
        request,
        "registration/register.html",
        {"form": form, "stats": platform_stats(), "nav_active": "register"},
    )


@never_cache
@require_http_methods(["GET", "POST"])
def login(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request) or request.user.dashboard_url)

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = services.login(
                request=request,
                identifier=form.cleaned_data["identifier"],
                password=form.cleaned_data["password"],
            )
        except DomainError as exc:
            messages.error(request, exc.message)
        else:
            django_login(
                request, user, backend="apps.accounts.backends.EmailOrUsernameBackend"
            )
            if not form.cleaned_data.get("remember"):
                request.session.set_expiry(0)  # expire with the browser session
            return redirect(_safe_next(request) or user.dashboard_url)

    return render(
        request,
        "registration/login.html",
        {
            "form": form,
            "stats": platform_stats(),
            "next": _safe_next(request) or "",
            "nav_active": "login",
        },
    )


@require_http_methods(["POST"])
def logout(request):
    django_logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("home")


@never_cache
@require_http_methods(["GET", "POST"])
def verify_notice(request):
    if request.user.is_authenticated and request.user.is_email_verified:
        return redirect(request.user.dashboard_url)

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        try:
            user = services.verify_code(
                code=code,
                user=request.user if request.user.is_authenticated else None,
            )
            messages.success(
                request, "Email verified successfully! Your account is now fully active."
            )
            if not request.user.is_authenticated:
                django_login(
                    request, user, backend="apps.accounts.backends.EmailOrUsernameBackend"
                )
            return redirect(user.dashboard_url)
        except DomainError as exc:
            messages.error(request, exc.message)
            return render(request, "registration/verify_notice.html", {"code": code})

    return render(request, "registration/verify_notice.html")


@require_http_methods(["POST"])
def resend_verification(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    try:
        services.send_verification_email(user=request.user)
        messages.success(request, f"Verification email sent to {request.user.email}.")
    except DomainError as exc:
        messages.error(request, exc.message)
    return redirect(
        request.META.get("HTTP_REFERER") or reverse("accounts:verify_notice")
    )


@never_cache
def verify_email(request, token: str):
    try:
        user = services.verify_email(token=token)
    except DomainError as exc:
        messages.error(request, exc.message)
        return render(
            request,
            "registration/verify_failed.html",
            {"error": exc.message},
            status=400,
        )

    messages.success(request, "Email verified — your account is fully active.")
    if request.user.is_authenticated and request.user.pk == user.pk:
        return redirect(user.dashboard_url)
    return redirect("accounts:login")


@never_cache
@require_http_methods(["GET", "POST"])
def settings_view(request):
    """Account settings: name, username, avatar and password."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    profile_form = AccountSettingsForm(
        request.POST if request.POST.get("form") == "profile" else None,
        request.FILES if request.POST.get("form") == "profile" else None,
        initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "username": request.user.username,
        },
    )
    password_form = ChangePasswordForm(
        request.POST if request.POST.get("form") == "password" else None
    )

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "profile" and profile_form.is_valid():
            from apps.accounts.models import User

            data = profile_form.cleaned_data
            taken = (
                User.objects.filter(username=data["username"])
                .exclude(pk=request.user.pk)
                .exists()
            )
            if taken:
                profile_form.add_error("username", "That username is taken.")
            else:
                user = request.user
                user.first_name = data["first_name"]
                user.last_name = data["last_name"]
                user.username = data["username"]
                if data.get("avatar"):
                    from apps.core.validators import validate_image

                    user.avatar = validate_image(data["avatar"])
                user.save()
                messages.success(request, "Settings saved.")
                return redirect("accounts:settings")

        elif which == "password" and password_form.is_valid():
            try:
                services.change_password(
                    user=request.user,
                    current_password=password_form.cleaned_data["current_password"],
                    new_password=password_form.cleaned_data["new_password"],
                )
            except DomainError as exc:
                messages.error(request, exc.message)
                for field, errors in getattr(exc, "errors", {}).items():
                    password_form.add_error(
                        field if field in password_form.fields else None,
                        errors if isinstance(errors, str) else "; ".join(errors),
                    )
            else:
                # Keep the current session valid after a password change.
                from django.contrib.auth import update_session_auth_hash

                update_session_auth_hash(request, request.user)
                messages.success(request, "Password updated.")
                return redirect("accounts:settings")

    return render(
        request,
        "registration/settings.html",
        {
            "profile_form": profile_form,
            "password_form": password_form,
            "prefs": None,
            "prefs_fields": NOTIFICATION_PREF_FIELDS,
            "page_title": "Account settings",
        },
    )


@require_http_methods(["POST"])
def update_notification_prefs(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    messages.success(request, "Notification preferences saved.")
    return redirect("accounts:settings")
