"""The SkillCoin wallet and its ledger.

Two invariants are enforced by database ``CheckConstraint``s rather than only
in Python, because a partial financial state must be impossible — even if some
future code path forgets to go through the service layer, the database refuses
the write:

* no balance bucket may go negative;
* a ledger row's amount must be positive, with direction carried by the bucket
pair, so an "amount" can never be read with the wrong sign.

Every row also records the wallet total before and after, which is what lets
the ledger be replayed and checked against the stored balances.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField, SignedMoneyField


class Wallet(TimeStampedModel):
    """Three-bucket balance model.

    * ``available_balance`` — spendable right now
    * ``reserved_balance``  — locked against a published job budget or a
    pending withdrawal; still the user's money, but not spendable
    * ``escrow_balance``    — committed to a funded project, in neither
    party's control until a release or a refund
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wallet"
    )
    available_balance = MoneyField(help_text="Spendable SkillCoin.")
    reserved_balance = MoneyField(
        help_text="Locked for published job budgets or a pending withdrawal."
    )
    escrow_balance = MoneyField(help_text="Committed to funded projects.")

    lifetime_deposited = MoneyField()
    lifetime_withdrawn = MoneyField()
    lifetime_earned = MoneyField()
    lifetime_spent = MoneyField()

    is_frozen = models.BooleanField(
        default=False, help_text="Admin freeze — blocks every outgoing movement."
    )
    frozen_reason = models.CharField(max_length=300, blank=True)
    version = models.PositiveBigIntegerField(
        default=0, help_text="Incremented on every mutation; detects lost updates."
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(available_balance__gte=ZERO),
                name="wallet_available_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(reserved_balance__gte=ZERO),
                name="wallet_reserved_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(escrow_balance__gte=ZERO),
                name="wallet_escrow_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"wallet<{self.user_id}>"

    @property
    def total(self):
        return self.available_balance + self.reserved_balance + self.escrow_balance

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Wallet user={self.user_id} available={self.available_balance} "
            f"reserved={self.reserved_balance} escrow={self.escrow_balance}>"
        )


def _internal_txn_id() -> str:
    """Human-quotable internal reference."""
    return f"SB-{timezone.now():%y%m%d}-{secrets.token_hex(4).upper()}"


class WalletTransaction(BaseModel):
    """Append-only double-entry-style ledger.

    Rows are never updated once ``COMPLETED``; a correction is a new,
    ``related``-linked row.  ``balance_before``/``balance_after`` snapshot the
    bucket this row moved, which lets ``finance`` reconcile the whole ledger
    against the wallet without replaying business logic.
    """

    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        BUDGET_RESERVATION = "BUDGET_RESERVATION", "Job budget reserved"
        BUDGET_RELEASE = "BUDGET_RELEASE", "Job budget released"
        ESCROW_HOLD = "ESCROW_HOLD", "Escrow hold"
        ESCROW_RELEASE = "ESCROW_RELEASE", "Escrow released"
        PROJECT_PAYMENT = "PROJECT_PAYMENT", "Project payment"
        REFUND = "REFUND", "Refund"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        WITHDRAWAL_REVERSAL = "WITHDRAWAL_REVERSAL", "Withdrawal reversal"
        ADJUSTMENT = "ADJUSTMENT", "Administrative adjustment"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REVERSED = "REVERSED", "Reversed"

    class Bucket(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        ESCROW = "ESCROW", "Escrow"
        EXTERNAL = "EXTERNAL", "External"

    internal_transaction_id = models.CharField(
        max_length=32,
        unique=True,
        default=_internal_txn_id,
        editable=False,
        db_index=True,
    )
    wallet = models.ForeignKey(
        Wallet, on_delete=models.PROTECT, related_name="transactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet_transactions",
    )

    transaction_type = models.CharField(
        max_length=22, choices=Type.choices, db_index=True
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.COMPLETED, db_index=True
    )

    amount = MoneyField(
        help_text="Always positive; direction is implied by from/to bucket."
    )
    delta = SignedMoneyField(
        help_text="Signed effect on the wallet total (0 for internal bucket moves)."
    )
    from_bucket = models.CharField(max_length=10, choices=Bucket.choices)
    to_bucket = models.CharField(max_length=10, choices=Bucket.choices)

    balance_before = MoneyField(help_text="Wallet total before this row.")
    balance_after = MoneyField(help_text="Wallet total after this row.")
    available_after = MoneyField()
    reserved_after = MoneyField()
    escrow_after = MoneyField()

    job_id = models.PositiveIntegerField(null=True, blank=True)
    project_id = models.PositiveIntegerField(null=True, blank=True)
    task_id = models.PositiveIntegerField(null=True, blank=True)
    counterparty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counterparty_transactions",
    )
    related_transaction = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="linked"
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actioned_transactions",
        help_text="Admin or user who triggered this row; null for scheduled jobs.",
    )
    description = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["transaction_type", "-created_at"]),
            models.Index(fields=["project_id", "-created_at"]),
            models.Index(fields=["status", "transaction_type"]),
            models.Index(fields=["internal_transaction_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=ZERO), name="ledger_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.internal_transaction_id} {self.transaction_type} {self.amount}"

    @property
    def is_credit(self) -> bool:
        return self.delta > ZERO

    @property
    def is_debit(self) -> bool:
        return self.delta < ZERO

    @property
    def direction(self) -> str:
        if self.delta > ZERO:
            return "in"
        if self.delta < ZERO:
            return "out"
        return "internal"


def _deposit_ref() -> str:
    """Human-readable deposit reference."""
    return f"DEP-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


class Deposit(BaseModel):
    """Deposit record: adds spendable SkillCoin to the user's wallet."""

    class Method(models.TextChoices):
        BKASH = "BKASH", "bKash"
        NAGAD = "NAGAD", "Nagad"
        BANK = "BANK", "Bank Transfer"
        TEST = "TEST", "Instant Sandbox / Test Deposit"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Verification"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    reference_id = models.CharField(
        max_length=32,
        unique=True,
        default=_deposit_ref,
        editable=False,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="deposits",
    )
    amount = MoneyField(help_text="Amount in BDT / SkillCoin.")
    payment_method = models.CharField(
        max_length=10, choices=Method.choices, default=Method.BKASH
    )
    sender_number = models.CharField(
        max_length=30, blank=True, help_text="Mobile or account number used to send money."
    )
    transaction_id = models.CharField(
        max_length=100, blank=True, help_text="Provider's transaction ID (e.g. bKash TrxID)."
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    admin_note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_deposits",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference_id} - {self.user.username} - {self.amount}"

    def get_payment_method_display_name(self) -> str:
        return dict(self.Method.choices).get(self.payment_method, self.payment_method)


def _withdrawal_ref() -> str:
    """Human-readable withdrawal reference."""
    return f"WDR-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


class Withdrawal(BaseModel):
    """Withdrawal request: payout SkillCoin from user's available balance to real account."""

    class Method(models.TextChoices):
        BKASH = "BKASH", "bKash"
        NAGAD = "NAGAD", "Nagad"
        BANK = "BANK", "Bank Transfer"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Verification"
        APPROVED = "APPROVED", "Approved & Paid"
        REJECTED = "REJECTED", "Rejected"

    reference_id = models.CharField(
        max_length=32,
        unique=True,
        default=_withdrawal_ref,
        editable=False,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="withdrawals",
    )
    amount = MoneyField(help_text="Amount in SkillCoin / BDT.")
    payment_method = models.CharField(
        max_length=10, choices=Method.choices, default=Method.BKASH
    )
    account_number = models.CharField(
        max_length=50, help_text="Mobile banking number or Bank account details."
    )
    account_name = models.CharField(
        max_length=100, blank=True, help_text="Account holder name."
    )
    external_transaction_id = models.CharField(
        max_length=100, blank=True, help_text="Transaction ID / reference from provider."
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    admin_note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_withdrawals",
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference_id} - {self.user.username} - {self.amount}"

    def get_payment_method_display(self) -> str:
        return dict(self.Method.choices).get(self.payment_method, self.payment_method)

    def get_payment_method_display_name(self) -> str:
        return dict(self.Method.choices).get(self.payment_method, self.payment_method)

