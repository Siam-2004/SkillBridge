"""Escrow monitoring."""

from django.contrib import admin

from apps.escrow.models import Escrow, EscrowAllocation


class EscrowAllocationInline(admin.TabularInline):
    model = EscrowAllocation
    extra = 0
    readonly_fields = (
        "task",
        "freelancer",
        "amount",
        "status",
        "trigger",
        "released_at",
        "released_by",
        "debit_transaction",
        "credit_transaction",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "project",
        "client",
        "funded_amount",
        "held_amount",
        "released_amount",
        "refunded_amount",
        "status",
        "is_locked",
    )
    list_filter = ("status", "is_locked", "funded_at")
    search_fields = ("public_id", "project__title", "client__email")
    autocomplete_fields = ("project", "client", "agreement")
    date_hierarchy = "funded_at"
    inlines = [EscrowAllocationInline]

    # Amounts are maintained by escrow.services alongside the ledger rows.
    readonly_fields = (
        "public_id",
        "project",
        "client",
        "agreement",
        "funded_amount",
        "held_amount",
        "released_amount",
        "refunded_amount",
        "status",
        "funded_at",
        "released_at",
        "disputed_at",
        "hold_transaction",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields + ("is_locked", "lock_reason")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EscrowAllocation)
class EscrowAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "escrow",
        "task",
        "freelancer",
        "amount",
        "status",
        "trigger",
        "released_at",
    )
    list_filter = ("status", "trigger", "created_at")
    search_fields = ("escrow__public_id", "task__title", "freelancer__email")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in EscrowAllocation._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
