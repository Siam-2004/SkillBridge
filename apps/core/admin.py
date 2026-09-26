"""Admin for site configuration and the activity stream."""

from django.contrib import admin

from apps.core.models import ActivityLog, HomepageSection, SiteSetting


class ReadOnlyAdmin(admin.ModelAdmin):
    """A record that may be read but never edited or created here.

    Used for the history tables. If an operator could edit an activity row or
    an audit row, neither would be worth anything as evidence.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "group", "kind", "value", "is_public", "updated_at")
    list_filter = ("group", "kind", "is_public")
    search_fields = ("key", "label", "value")
    ordering = ("group", "key")
    fieldsets = (
        (None, {"fields": ("key", "label", "group")}),
        ("Value", {"fields": ("kind", "value", "help_text", "is_public")}),
    )


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    list_display = ("slot", "title", "sort_order", "is_active", "updated_at")
    list_filter = ("slot", "is_active")
    search_fields = ("title", "subtitle", "body")
    ordering = ("slot", "sort_order")
    list_editable = ("sort_order", "is_active")
    fieldsets = (
        (None, {"fields": ("slot", "is_active", "sort_order")}),
        ("Content", {"fields": ("title", "subtitle", "body", "icon", "image")}),
        ("Call to action", {"fields": ("button_text", "button_url")}),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "action", "actor", "description")
    list_filter = ("action", "visibility", "created_at")
    search_fields = ("description", "object_id", "actor__email")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("actor",)
