"""Negotiation and offer inspection."""

from django.contrib import admin

from apps.negotiations.models import Negotiation, Offer


class OfferInline(admin.TabularInline):
    model = Offer
    fk_name = "negotiation"
    extra = 0
    readonly_fields = (
        "sender",
        "receiver",
        "amount",
        "deadline",
        "revision_limit",
        "status",
        "created_at",
    )
    fields = readonly_fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Negotiation)
class NegotiationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "job",
        "client",
        "freelancer",
        "status",
        "current_offer",
    )
    list_filter = ("status", "created_at")
    search_fields = ("job__title", "client__email", "freelancer__email", "public_id")
    autocomplete_fields = ("job", "proposal", "client", "freelancer")
    date_hierarchy = "created_at"
    inlines = [OfferInline]
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "negotiation",
        "sender",
        "receiver",
        "amount",
        "status",
        "is_final",
        "expires_at",
    )
    list_filter = ("status", "is_final", "created_at")
    search_fields = ("negotiation__public_id", "sender__email", "receiver__email")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in Offer._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # An offer is a statement one party made at a moment in time. Editing
        # it would rewrite what somebody said.
        return False