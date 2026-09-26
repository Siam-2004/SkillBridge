"""Wallets and the ledger.

Financial history is read-only in the admin. A mistake is corrected with a new
adjustment transaction, never by editing a row — a ledger you can edit is not
a ledger.
"""

from django.contrib import admin

from apps.core.admin import ReadOnlyAdmin
from apps.wallets import services
from apps.wallets.models import Deposit, Wallet, WalletTransaction, Withdrawal


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "available_balance",
        "reserved_balance",
        "escrow_balance",
        "total_display",
        "is_frozen",
        "updated_at",
    )
    list_filter = ("is_frozen",)
    search_fields = ("user__email", "user__username")
    autocomplete_fields = ("user",)
    # Balances are only ever changed by wallets.ledger.move().
    readonly_fields = (
        "user",
        "available_balance",
        "reserved_balance",
        "escrow_balance",
        "lifetime_deposited",
        "lifetime_withdrawn",
        "lifetime_earned",
        "lifetime_spent",
        "version",
        "created_at",
        "updated_at",
    )
    fields = readonly_fields + ("is_frozen", "frozen_reason")

    @admin.display(description="Total")
    def total_display(self, obj):
        return obj.total

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(ReadOnlyAdmin):
    list_display = (
        "internal_transaction_id",
        "created_at",
        "user",
        "transaction_type",
        "amount",
        "delta",
        "from_bucket",
        "to_bucket",
        "balance_after",
        "status",
    )
    list_filter = (
        "transaction_type",
        "status",
        "from_bucket",
        "to_bucket",
        "created_at",
    )
    search_fields = (
        "internal_transaction_id",
        "user__email",
        "user__username",
        "description",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("user",)
    readonly_fields = [f.name for f in WalletTransaction._meta.fields]


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        "reference_id",
        "created_at",
        "user",
        "amount",
        "payment_method",
        "transaction_id",
        "status",
        "approved_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = (
        "reference_id",
        "transaction_id",
        "sender_number",
        "user__email",
        "user__username",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["approve_deposits", "reject_deposits"]

    @admin.action(description="Approve selected deposits and credit wallets")
    def approve_deposits(self, request, queryset):
        count = 0
        for deposit in queryset.filter(status=Deposit.Status.PENDING):
            services.approve_deposit(deposit=deposit, admin_user=request.user)
            count += 1
        self.message_user(request, f"Approved {count} deposit(s) and credited wallets.")

    @admin.action(description="Reject selected deposits")
    def reject_deposits(self, request, queryset):
        count = 0
        for deposit in queryset.filter(status=Deposit.Status.PENDING):
            services.reject_deposit(deposit=deposit, admin_user=request.user, reason="Admin rejected")
            count += 1
        self.message_user(request, f"Rejected {count} deposit(s).")


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = (
        "reference_id",
        "created_at",
        "user",
        "amount",
        "payment_method",
        "account_number",
        "external_transaction_id",
        "status",
        "processed_at",
    )
    list_filter = ("status", "payment_method", "created_at")
    search_fields = (
        "reference_id",
        "account_number",
        "external_transaction_id",
        "user__email",
        "user__username",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["approve_withdrawals", "reject_withdrawals"]

    @admin.action(description="Approve selected withdrawals and release funds")
    def approve_withdrawals(self, request, queryset):
        count = 0
        for w in queryset.filter(status=Withdrawal.Status.PENDING):
            services.approve_withdrawal(withdrawal=w, admin_user=request.user)
            count += 1
        self.message_user(request, f"Approved {count} withdrawal(s).")

    @admin.action(description="Reject selected withdrawals and return funds to available balance")
    def reject_withdrawals(self, request, queryset):
        count = 0
        for w in queryset.filter(status=Withdrawal.Status.PENDING):
            services.reject_withdrawal(withdrawal=w, admin_user=request.user, reason="Admin rejected")
            count += 1
        self.message_user(request, f"Rejected {count} withdrawal(s) and returned funds.")

