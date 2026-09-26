"""User administration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone

from apps.accounts.models import EmailVerificationToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "username",
        "full_name",
        "role",
        "status",
        "is_email_verified",
        "date_joined",
    )
    list_filter = ("role", "status", "is_email_verified", "is_staff", "date_joined")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("public_id", "date_joined", "last_login", "last_seen_at")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "avatar", "role")}),
        ("Trust", {"fields": ("is_email_verified", "email_verified_at")}),
        ("Standing", {"fields": ("status", "suspension_reason", "suspended_until")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Record",
            {"fields": ("public_id", "date_joined", "last_login", "last_seen_at")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "role", "password1", "password2"),
            },
        ),
    )

    actions = ["mark_verified", "suspend", "reinstate"]

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.full_name

    @admin.action(description="Mark the selected accounts as email-verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(
            is_email_verified=True, email_verified_at=timezone.now()
        )
        self.message_user(request, f"{updated} account(s) marked verified.")

    @admin.action(description="Suspend the selected accounts")
    def suspend(self, request, queryset):
        from apps.accounts.services import suspend_user

        done = 0
        for user in queryset:
            try:
                suspend_user(
                    user=user, admin=request.user, reason="Suspended from the admin."
                )
                done += 1
            except Exception as exc:
                self.message_user(request, f"{user.email}: {exc}", level="error")
        self.message_user(request, f"{done} account(s) suspended.")

    @admin.action(description="Reinstate the selected accounts")
    def reinstate(self, request, queryset):
        from apps.accounts.services import reinstate_user

        done = 0
        for user in queryset:
            try:
                reinstate_user(user=user, admin=request.user)
                done += 1
            except Exception as exc:
                self.message_user(request, f"{user.email}: {exc}", level="error")
        self.message_user(request, f"{done} account(s) reinstated.")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "user",
        "expires_at",
        "used_at",
        "sent_count",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("email", "user__email", "token")
    readonly_fields = ("token", "created_at", "updated_at")
    ordering = ("-created_at",)
