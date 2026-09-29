"""Notification inspection."""
from django.contrib import admin
from apps.notifications.models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "notification_type", "title", "read_at")
    list_filter = ("notification_type", "level", "created_at")
    search_fields = ("recipient__email", "title", "message")
    date_hierarchy = "created_at"
    autocomplete_fields = ("recipient", "actor")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_messages", "email_proposals", "email_tasks", "email_deadlines", "email_marketing")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)