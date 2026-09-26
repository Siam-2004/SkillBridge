"""Wallet-level operations that are not a deposit or a withdrawal.

Balance movements live in ``wallets.ledger``; deposits and withdrawals live in
``apps.payments``. What is left here is administration of the wallet itself and
the reconciliation check that proves stored balances still match the ledger.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import ValidationFailed
from apps.core.money import ZERO, positive_coin
from apps.core.permissions import require_admin
from apps.wallets import ledger
from apps.wallets.models import Deposit, Wallet, WalletTransaction, Withdrawal

logger = logging.getLogger("skillbridge.money")


@transaction.atomic()
def create_deposit(
    *,
    user,
    amount,
    payment_method: str = Deposit.Method.BKASH,
    sender_number: str = "",
    transaction_id: str = "",
) -> Deposit:
    """Create a deposit request. Requires Admin verification and approval before crediting."""
    coin_amount = positive_coin(amount)
    if coin_amount <= ZERO:
        raise ValidationFailed("Deposit amount must be positive.")

    deposit = Deposit.objects.create(
        user=user,
        amount=coin_amount,
        payment_method=payment_method,
        sender_number=sender_number.strip(),
        transaction_id=transaction_id.strip(),
        status=Deposit.Status.PENDING,
    )
    return deposit


@transaction.atomic()
def approve_deposit(*, deposit: Deposit | int, admin_user=None) -> Deposit:
    """Approve a deposit and credit the user's available balance in the ledger."""
    if isinstance(deposit, int):
        deposit = Deposit.objects.select_for_update().get(pk=deposit)
    else:
        deposit = Deposit.objects.select_for_update().get(pk=deposit.pk)

    if deposit.status == Deposit.Status.APPROVED:
        return deposit
    if deposit.status == Deposit.Status.REJECTED:
        raise ValidationFailed("Cannot approve a rejected deposit.")

    ledger.credit_deposit(
        user=deposit.user,
        amount=deposit.amount,
        actor=admin_user,
        deposit=deposit,
    )

    deposit.status = Deposit.Status.APPROVED
    deposit.approved_at = timezone.now()
    if admin_user:
        deposit.reviewed_by = admin_user
    deposit.save(update_fields=["status", "approved_at", "reviewed_by", "updated_at"])
    return deposit


@transaction.atomic()
def reject_deposit(*, deposit: Deposit | int, admin_user=None, reason: str = "") -> Deposit:
    """Reject a pending deposit request."""
    if isinstance(deposit, int):
        deposit = Deposit.objects.select_for_update().get(pk=deposit)
    else:
        deposit = Deposit.objects.select_for_update().get(pk=deposit.pk)

    if deposit.status == Deposit.Status.REJECTED:
        return deposit
    if deposit.status == Deposit.Status.APPROVED:
        raise ValidationFailed("Cannot reject an already approved deposit.")

    deposit.status = Deposit.Status.REJECTED
    deposit.admin_note = reason[:300]
    if admin_user:
        deposit.reviewed_by = admin_user
    deposit.save(update_fields=["status", "admin_note", "reviewed_by", "updated_at"])
    return deposit


@transaction.atomic()
def request_withdrawal(
    *,
    user,
    amount,
    payment_method: str = Withdrawal.Method.BKASH,
    account_number: str = "",
    account_name: str = "",
) -> Withdrawal:
    """Request a withdrawal from user's available balance into real currency.
    
    Reserves the funds immediately from available to reserved balance and creates
    a PENDING withdrawal request for Admin review and verification.
    """
    coin_amount = positive_coin(amount)
    if coin_amount <= ZERO:
        raise ValidationFailed("Withdrawal amount must be positive.")

    wallet = ledger.lock_wallet(user)
    if wallet.is_frozen:
        raise ValidationFailed(f"Wallet is frozen: {wallet.frozen_reason or 'contact support'}.")

    if wallet.available_balance < coin_amount:
        raise ValidationFailed(
            f"Insufficient funds. You have {wallet.available_balance} available SkillCoin."
        )

    withdrawal = Withdrawal.objects.create(
        user=user,
        amount=coin_amount,
        payment_method=payment_method,
        account_number=account_number.strip(),
        account_name=account_name.strip(),
        status=Withdrawal.Status.PENDING,
    )

    # Immediately lock funds from available to reserved
    ledger.reserve_withdrawal(
        user=user,
        amount=coin_amount,
        withdrawal=withdrawal,
        actor=user,
    )

    return withdrawal


@transaction.atomic()
def approve_withdrawal(
    *, withdrawal: Withdrawal | int, admin_user=None, transaction_id: str = ""
) -> Withdrawal:
    """Approve a withdrawal and release the reserved funds externally."""
    if isinstance(withdrawal, int):
        withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal)
    else:
        withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal.pk)

    if withdrawal.status == Withdrawal.Status.APPROVED:
        return withdrawal
    if withdrawal.status == Withdrawal.Status.REJECTED:
        raise ValidationFailed("Cannot approve a rejected withdrawal.")

    if transaction_id:
        withdrawal.external_transaction_id = transaction_id.strip()

    # Move from RESERVED to EXTERNAL
    ledger.payout_withdrawal(
        user=withdrawal.user,
        amount=withdrawal.amount,
        withdrawal=withdrawal,
        actor=admin_user,
    )

    withdrawal.status = Withdrawal.Status.APPROVED
    withdrawal.processed_at = timezone.now()
    if admin_user:
        withdrawal.reviewed_by = admin_user
    withdrawal.save(
        update_fields=[
            "status",
            "external_transaction_id",
            "processed_at",
            "reviewed_by",
            "updated_at",
        ]
    )
    return withdrawal


@transaction.atomic()
def reject_withdrawal(
    *, withdrawal: Withdrawal | int, admin_user=None, reason: str = ""
) -> Withdrawal:
    """Reject a withdrawal and return the reserved funds back to available balance."""
    if isinstance(withdrawal, int):
        withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal)
    else:
        withdrawal = Withdrawal.objects.select_for_update().get(pk=withdrawal.pk)

    if withdrawal.status == Withdrawal.Status.REJECTED:
        return withdrawal
    if withdrawal.status == Withdrawal.Status.APPROVED:
        raise ValidationFailed("Cannot reject an already completed withdrawal.")

    # Move from RESERVED back to AVAILABLE
    ledger.reverse_withdrawal(
        user=withdrawal.user,
        amount=withdrawal.amount,
        withdrawal=withdrawal,
        actor=admin_user,
        reason=reason,
    )

    withdrawal.status = Withdrawal.Status.REJECTED
    withdrawal.admin_note = reason[:300]
    withdrawal.processed_at = timezone.now()
    if admin_user:
        withdrawal.reviewed_by = admin_user
    withdrawal.save(
        update_fields=[
            "status",
            "admin_note",
            "processed_at",
            "reviewed_by",
            "updated_at",
        ]
    )
    return withdrawal


@transaction.atomic()
def set_wallet_frozen(*, user, admin, frozen: bool, reason: str = "") -> Wallet:
    require_admin(admin)
    if frozen and not reason.strip():
        raise ValidationFailed("Freezing a wallet requires a reason.")
    wallet = ledger.lock_wallet(user)
    wallet.is_frozen = frozen
    wallet.frozen_reason = reason[:300] if frozen else ""
    wallet.save(update_fields=["is_frozen", "frozen_reason", "updated_at"])
    return wallet


def reconcile_wallets(*, limit: int | None = None) -> dict:
    """Re-derive every wallet from its ledger rows and report disagreements.

    A discrepancy should be impossible: the ledger row and the balance update
    are written in the same transaction. If one ever appears, the platform has
    a bug and an operator needs to know, so this is run by
    ``python manage.py reconcile_wallets`` and shown in the admin.
    """
    details: list[dict] = []
    checked = 0
    total_difference = ZERO

    qs = Wallet.objects.select_related("user").order_by("pk")
    if limit:
        qs = qs[:limit]

    for wallet in qs.iterator(chunk_size=200):
        checked += 1
        ledger_total = (
            WalletTransaction.objects.filter(
                user_id=wallet.user_id, status=WalletTransaction.Status.COMPLETED
            ).aggregate(t=Sum("delta"))["t"]
            or ZERO
        )
        stored = (
            wallet.available_balance + wallet.reserved_balance + wallet.escrow_balance
        )
        if stored != ledger_total:
            difference = stored - ledger_total
            total_difference += difference
            details.append(
                {
                    "user": wallet.user.email,
                    "stored_total": str(stored),
                    "ledger_total": str(ledger_total),
                    "difference": str(difference),
                }
            )

    if details:
        logger.error(
            "LEDGER DISCREPANCY: %s wallet(s) out of balance by %s",
            len(details),
            total_difference,
        )
    return {
        "balanced": not details,
        "wallets_checked": checked,
        "discrepancy_count": len(details),
        "total_difference": total_difference,
        "details": details[:200],
    }
