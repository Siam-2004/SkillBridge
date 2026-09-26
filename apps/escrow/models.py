"""Escrow: money committed to a project and no longer either party's to spend.

Escrow is the platform's promise in table form. Once a client funds a project,
the coins leave their spendable balance and sit here until a task is approved,
a project is completed, or a dispute is resolved. Two consequences follow, and
both are enforced by database constraints rather than by convention:

* the four amounts must always reconcile — what was funded equals what is still
  held plus what has been released plus what has been refunded;
* a task payment is drawn from ``held_amount`` and never from the client's
  available balance, so a client cannot be charged twice for the same work.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField


class Escrow(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PARTIALLY_RELEASED = "PARTIALLY_RELEASED", "Partially released"
        RELEASED = "RELEASED", "Released"
        DISPUTED = "DISPUTED", "Disputed"
        REFUNDED = "REFUNDED", "Refunded"

    project = models.OneToOneField(
        "projects.Project", on_delete=models.PROTECT, related_name="escrow"
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="escrows"
    )
    agreement = models.ForeignKey(
        "agreements.Agreement", on_delete=models.PROTECT, related_name="escrows"
    )

    funded_amount = MoneyField(
        help_text="Total ever placed in escrow for this project."
    )
    held_amount = MoneyField(help_text="Still locked.")
    released_amount = MoneyField(help_text="Paid out to freelancers.")
    refunded_amount = MoneyField(help_text="Returned to the client.")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    funded_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)

    hold_transaction = models.ForeignKey(
        "wallets.WalletTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_holds",
    )

    is_locked = models.BooleanField(
        default=False, help_text="An open dispute freezes every movement."
    )
    lock_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(held_amount__gte=ZERO), name="escrow_held_non_negative"
            ),
            # The three parts must always account for exactly what was funded.
            models.CheckConstraint(
                check=models.Q(
                    funded_amount=models.F("held_amount")
                    + models.F("released_amount")
                    + models.F("refunded_amount")
                ),
                name="escrow_balances_reconcile",
            ),
        ]

    def __str__(self) -> str:
        return f"escrow<{self.public_id}> {self.held_amount}/{self.funded_amount}"

    @property
    def amount(self):
        """What the client committed. The specification's ``Escrow.amount``."""
        return self.funded_amount

    @property
    def is_exhausted(self) -> bool:
        return self.held_amount <= ZERO

    @property
    def release_percent(self) -> int:
        if self.funded_amount <= ZERO:
            return 0
        return int(self.released_amount / self.funded_amount * 100)

    @property
    def allocated_total(self):
        """SUM of the task allocations currently attached to this project."""
        from django.db.models import Sum

        from apps.tasks.models import Task

        return (
            Task.objects.filter(project_id=self.project_id)
            .exclude(status=Task.Status.CANCELLED)
            .aggregate(total=Sum("skillcoin_allocation"))["total"]
            or ZERO
        )

    @property
    def unallocated_amount(self):
        return self.funded_amount - self.allocated_total

    @property
    def allocations_balanced(self) -> bool:
        """Allocations must match escrow exactly before any final release."""
        return self.allocated_total == self.funded_amount


class EscrowAllocation(TimeStampedModel):
    """One task's share of the escrow, and the record of it being paid.

    Created when a task is given an allocation and settled when that task's
    payment is released, so this table answers both "how is the money split?"
    and "what has actually been paid, to whom, and why?" — which is exactly
    what a dispute needs to see.
    """

    class Status(models.TextChoices):
        ALLOCATED = "ALLOCATED", "Allocated"
        RELEASED = "RELEASED", "Released"
        REFUNDED = "REFUNDED", "Refunded"
        CANCELLED = "CANCELLED", "Cancelled"

    class Trigger(models.TextChoices):
        CLIENT_APPROVAL = "CLIENT_APPROVAL", "Client approved"
        AUTO_RELEASE = "AUTO_RELEASE", "48-hour rule"
        PROJECT_APPROVAL = "PROJECT_APPROVAL", "Final project approval"
        DISPUTE_RESOLUTION = "DISPUTE_RESOLUTION", "Dispute resolution"
        ADMIN_RELEASE = "ADMIN_RELEASE", "Administrator release"

    escrow = models.ForeignKey(
        Escrow, on_delete=models.CASCADE, related_name="allocations"
    )
    task = models.OneToOneField(
        "tasks.Task",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allocation_record",
        help_text="Null for the final, non-task payment of any remainder.",
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="escrow_allocations",
    )
    amount = MoneyField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ALLOCATED, db_index=True
    )
    released_at = models.DateTimeField(null=True, blank=True)

    trigger = models.CharField(max_length=20, choices=Trigger.choices, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="released_allocations",
    )
    note = models.CharField(max_length=300, blank=True)

    debit_transaction = models.ForeignKey(
        "wallets.WalletTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocation_debits",
    )
    credit_transaction = models.ForeignKey(
        "wallets.WalletTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocation_credits",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["escrow", "-created_at"]),
            models.Index(fields=["status", "-released_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=ZERO), name="allocation_amount_positive"
            ),
            # A released allocation must name the ledger rows that paid it.
            # Without this, "RELEASED" could be set with no money having moved.
            models.CheckConstraint(
                check=models.Q(status="RELEASED", credit_transaction__isnull=False)
                | ~models.Q(status="RELEASED"),
                name="allocation_released_requires_transaction",
            ),
        ]

    def __str__(self) -> str:
        return f"allocation<{self.task_id or 'remainder'}> {self.amount}"

    @property
    def is_released(self) -> bool:
        return self.status == self.Status.RELEASED
