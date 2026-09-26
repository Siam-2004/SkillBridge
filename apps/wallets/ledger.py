"""The **only** code in Skillbridge permitted to change a wallet balance. forbids ``wallet.available_balance += amount`` anywhere in business logic.  Every
movement goes through :func:`move`, which performs, inside a single
``transaction.atomic()`` block:

    validation → row lock → balance update → ledger row → audit row → commit

Notification is fired by the caller after commit, because a notification is a
business event, not part of the balance change.

Callers never construct :class:`WalletTransaction` themselves — if a new kind of
movement is needed, add a named helper *here* so the invariants stay in one
place and the ledger stays complete.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.core.exceptions import (
    FinancialError,
    InsufficientFunds,
    ValidationFailed,
)
from apps.core.money import ZERO, positive_coin
from apps.core.services import _jsonable
from apps.wallets.models import Wallet, WalletTransaction

logger = logging.getLogger("skillbridge.money")

Bucket = WalletTransaction.Bucket
Type = WalletTransaction.Type

BUCKET_FIELD = {
    Bucket.AVAILABLE: "available_balance",
    Bucket.RESERVED: "reserved_balance",
    Bucket.ESCROW: "escrow_balance",
}


def lock_wallet(user_or_wallet) -> Wallet:
    """``SELECT … FOR UPDATE`` the wallet row.

    Serialises concurrent money operations on the same wallet: two browser tabs
    publishing two jobs cannot both pass the "enough available balance" check
    against the same coins.
    """
    if isinstance(user_or_wallet, Wallet):
        wallet_id = user_or_wallet.pk
    else:
        wallet, _ = Wallet.objects.get_or_create(user=user_or_wallet)
        wallet_id = wallet.pk
    return Wallet.objects.select_for_update().get(pk=wallet_id)


def lock_wallets(*users) -> dict[int, Wallet]:
    """Lock several wallets in a deterministic order to avoid deadlock.

    A payment release touches the client's escrow and the freelancer's
    available balance in the same transaction; always taking the locks in
    ascending primary-key order means two simultaneous releases can never each
    hold the lock the other needs.
    """
    ids = sorted({u.pk for u in users if u is not None})
    wallets = {}
    for uid in ids:
        wallet, _ = Wallet.objects.get_or_create(user_id=uid)
        wallets[uid] = Wallet.objects.select_for_update().get(pk=wallet.pk)
    return wallets


@transaction.atomic()
def move(
    *,
    user,
    amount,
    transaction_type: str,
    from_bucket: str,
    to_bucket: str,
    wallet: Wallet | None = None,
    actor=None,
    description: str = "",
    job=None,
    project=None,
    task=None,
    counterparty=None,
    related: WalletTransaction | None = None,
    reason: str = "",
    allow_frozen: bool = False,
    **metadata,
) -> WalletTransaction:
    """Move ``amount`` between two buckets of one wallet and record it.

    ``EXTERNAL`` as the source means new SkillCoin entering the platform (an
    approved deposit); ``EXTERNAL`` as the destination means coin leaving it (a
    completed payout).  Anything else is an internal bucket move and leaves the
    wallet total unchanged.
    """
    amount = positive_coin(amount)

    if from_bucket == to_bucket:
        raise FinancialError("A movement must change bucket.")
    if from_bucket == Bucket.EXTERNAL and to_bucket == Bucket.EXTERNAL:
        raise FinancialError("A movement must touch the wallet.")

    wallet = wallet if wallet is not None else lock_wallet(user)
    if wallet.is_frozen and not allow_frozen and from_bucket != Bucket.EXTERNAL:
        raise FinancialError(
            f"This wallet is frozen: {wallet.frozen_reason or 'contact support'}."
        )

    before_total = wallet.total
    before_snapshot = {
        "available": str(wallet.available_balance),
        "reserved": str(wallet.reserved_balance),
        "escrow": str(wallet.escrow_balance),
    }

    # ---- debit side --------------------------------------------------- #
    if from_bucket != Bucket.EXTERNAL:
        field = BUCKET_FIELD[from_bucket]
        current: Decimal = getattr(wallet, field)
        if current < amount:
            raise InsufficientFunds(
                required=amount,
                available=current,
                code=f"insufficient_{field}",
            )
        setattr(wallet, field, current - amount)

    # ---- credit side -------------------------------------------------- #
    if to_bucket != Bucket.EXTERNAL:
        field = BUCKET_FIELD[to_bucket]
        setattr(wallet, field, getattr(wallet, field) + amount)

    # Lifetime counters — reporting only, never used for authorisation.
    if from_bucket == Bucket.EXTERNAL:
        wallet.lifetime_deposited += amount
    if to_bucket == Bucket.EXTERNAL:
        wallet.lifetime_withdrawn += amount
    if transaction_type == Type.PROJECT_PAYMENT:
        wallet.lifetime_earned += amount
    if transaction_type == Type.ESCROW_HOLD:
        wallet.lifetime_spent += amount

    wallet.version = F("version") + 1
    wallet.save(
        update_fields=[
            "available_balance",
            "reserved_balance",
            "escrow_balance",
            "version",
            "updated_at",
            "lifetime_deposited",
            "lifetime_withdrawn",
            "lifetime_earned",
            "lifetime_spent",
        ]
    )
    wallet.refresh_from_db(
        fields=["version", "available_balance", "reserved_balance", "escrow_balance"]
    )

    after_total = wallet.total
    delta = after_total - before_total

    txn = WalletTransaction.objects.create(
        wallet=wallet,
        user=wallet.user,
        transaction_type=transaction_type,
        status=WalletTransaction.Status.COMPLETED,
        amount=amount,
        delta=delta,
        from_bucket=from_bucket,
        to_bucket=to_bucket,
        balance_before=before_total,
        balance_after=after_total,
        available_after=wallet.available_balance,
        reserved_after=wallet.reserved_balance,
        escrow_after=wallet.escrow_balance,
        job_id=getattr(job, "id", job) if job else None,
        project_id=getattr(project, "id", project) if project else None,
        task_id=getattr(task, "id", task) if task else None,
        counterparty=counterparty,
        related_transaction=related,
        actor=actor,
        description=description[:300],
        # Callers pass model instances (job, deposit, withdrawal) as context;
        # normalise them to public ids so the JSON column stays serialisable.
        metadata=_jsonable(metadata),
    )

    logger.info(
        "ledger %s user=%s %s→%s amount=%s total=%s→%s txn=%s",
        transaction_type,
        wallet.user_id,
        from_bucket,
        to_bucket,
        amount,
        before_total,
        after_total,
        txn.internal_transaction_id,
    )
    return txn


# --------------------------------------------------------------------------- #
# Named movements.  Business code calls these, never ``move`` directly, so the
# set of legal balance movements in the platform is this list and nothing else.
# --------------------------------------------------------------------------- #
def credit_deposit(
    *, user, amount, actor=None, deposit=None, **kw
) -> WalletTransaction:
    """EXTERNAL → available. New coin enters, after admin verification."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.DEPOSIT,
        from_bucket=Bucket.EXTERNAL,
        to_bucket=Bucket.AVAILABLE,
        actor=actor,
        description=(
            f"Deposit approved ({deposit.get_payment_method_display()})"
            if deposit
            else "Deposit approved"
        ),
        external_transaction_id=getattr(deposit, "external_transaction_id", ""),
        deposit=deposit,
        **kw,
    )


def reserve_job_budget(*, user, amount, job, actor=None, **kw) -> WalletTransaction:
    """available → reserved when a job is published."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.BUDGET_RESERVATION,
        from_bucket=Bucket.AVAILABLE,
        to_bucket=Bucket.RESERVED,
        job=job,
        actor=actor,
        description=f"Budget reserved for job “{job.title[:80]}”",
        **kw,
    )


def release_job_budget(
    *, user, amount, job, actor=None, reason="", **kw
) -> WalletTransaction:
    """reserved → available when a job is cancelled before hire."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.BUDGET_RELEASE,
        from_bucket=Bucket.RESERVED,
        to_bucket=Bucket.AVAILABLE,
        job=job,
        actor=actor,
        reason=reason,
        description=f"Reserved budget released for job “{job.title[:80]}”",
        **kw,
    )


def hold_escrow(
    *, user, amount, project, job=None, actor=None, **kw
) -> WalletTransaction:
    """reserved → escrow when the client funds the agreement.

    The coins are already reserved against the job, so funding a project never
    re-charges the client's available balance.
    """
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.ESCROW_HOLD,
        from_bucket=Bucket.RESERVED,
        to_bucket=Bucket.ESCROW,
        project=project,
        job=job,
        actor=actor,
        description=f"Escrow funded for project “{project.title[:80]}”",
        **kw,
    )


def hold_escrow_from_available(
    *, user, amount, project, job=None, actor=None, **kw
) -> WalletTransaction:
    """available → escrow — used only for a top-up after an agreed increase."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.ESCROW_HOLD,
        from_bucket=Bucket.AVAILABLE,
        to_bucket=Bucket.ESCROW,
        project=project,
        job=job,
        actor=actor,
        description=f"Escrow top-up for project “{project.title[:80]}”",
        **kw,
    )


def release_payment(
    *,
    client,
    freelancer,
    amount,
    project,
    task=None,
    actor=None,
    automatic: bool = False,
    **kw,
) -> tuple[WalletTransaction, WalletTransaction]:
    """escrow → freelancer available. The rule, implemented literally.

    Two ledger rows are written and linked: the client's escrow is debited and
    the freelancer's available balance is credited by the same amount.  The
    client's *available* balance is never touched, because the money was already
    committed when escrow was funded.
    """
    amount = positive_coin(amount)
    label = "Automatic release" if automatic else "Payment released"
    detail = f" for task “{task.title[:60]}”" if task is not None else ""

    debit = move(
        user=client,
        amount=amount,
        transaction_type=Type.ESCROW_RELEASE,
        from_bucket=Bucket.ESCROW,
        to_bucket=Bucket.EXTERNAL,
        project=project,
        task=task,
        counterparty=freelancer,
        actor=actor,
        description=f"{label}{detail}",
        automatic=automatic,
        **kw,
    )
    credit = move(
        user=freelancer,
        amount=amount,
        transaction_type=Type.PROJECT_PAYMENT,
        from_bucket=Bucket.EXTERNAL,
        to_bucket=Bucket.AVAILABLE,
        project=project,
        task=task,
        counterparty=client,
        actor=actor,
        related=debit,
        description=f"{label}{detail}",
        automatic=automatic,
        **kw,
    )
    # Link both directions so either row leads an auditor to its pair.
    WalletTransaction.objects.filter(pk=debit.pk).update(related_transaction=credit)
    debit.refresh_from_db(fields=["related_transaction"])
    return debit, credit


def refund_escrow(
    *, client, amount, project, actor=None, reason: str = "", **kw
) -> WalletTransaction:
    """escrow → client available, on cancellation or a dispute ruling."""
    return move(
        user=client,
        amount=amount,
        transaction_type=Type.REFUND,
        from_bucket=Bucket.ESCROW,
        to_bucket=Bucket.AVAILABLE,
        project=project,
        actor=actor,
        reason=reason,
        description=f"Refund for project “{project.title[:80]}”",
        **kw,
    )


def reserve_withdrawal(
    *, user, amount, withdrawal=None, actor=None, **kw
) -> WalletTransaction:
    """available → reserved the moment a payout is requested."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.WITHDRAWAL,
        from_bucket=Bucket.AVAILABLE,
        to_bucket=Bucket.RESERVED,
        actor=actor,
        description="Withdrawal requested",
        withdrawal=withdrawal,
        **kw,
    )


def payout_withdrawal(
    *, user, amount, withdrawal, actor=None, **kw
) -> WalletTransaction:
    """reserved → EXTERNAL once the operator has actually sent the money."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.WITHDRAWAL,
        from_bucket=Bucket.RESERVED,
        to_bucket=Bucket.EXTERNAL,
        actor=actor,
        description=f"Withdrawal paid out ({withdrawal.get_payment_method_display()})",
        external_transaction_id=withdrawal.external_transaction_id,
        withdrawal=withdrawal,
        **kw,
    )


def reverse_withdrawal(
    *, user, amount, withdrawal, actor=None, reason: str = "", **kw
) -> WalletTransaction:
    """reserved → available when a payout is rejected."""
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.WITHDRAWAL_REVERSAL,
        from_bucket=Bucket.RESERVED,
        to_bucket=Bucket.AVAILABLE,
        actor=actor,
        reason=reason,
        description="Withdrawal request rejected — funds returned",
        withdrawal=withdrawal,
        **kw,
    )


def adjust(
    *, user, amount, bucket: str, credit: bool, actor, reason: str, **kw
) -> WalletTransaction:
    """Administrative correction — always requires an actor and a reason."""
    if not reason.strip():
        raise ValidationFailed("An adjustment requires a written reason.")
    if not actor or not actor.is_platform_admin:
        raise FinancialError("Only an administrator can post an adjustment.")
    return move(
        user=user,
        amount=amount,
        transaction_type=Type.ADJUSTMENT,
        from_bucket=Bucket.EXTERNAL if credit else bucket,
        to_bucket=bucket if credit else Bucket.EXTERNAL,
        actor=actor,
        reason=reason,
        description=f"Administrative adjustment: {reason[:200]}",
        allow_frozen=True,
        **kw,
    )


# The specification names these entry points; they are the public API of the
# money layer and the only names business code should need to know.
move_available_to_escrow = hold_escrow_from_available
release_escrow_to_freelancer = release_payment
complete_withdrawal = payout_withdrawal
reject_withdrawal = reverse_withdrawal


def verify_ledger(user) -> dict:
    """Recompute the wallet total from the ledger and compare.

    If the sum of every signed delta does not equal the stored total, the
    platform has a bug and the operator needs to know. Surfaced in the admin
    and by ``python manage.py reconcile_wallets``.
    """
    from django.db.models import Sum

    wallet = Wallet.objects.get(user=user)
    ledger_total = (
        WalletTransaction.objects.filter(
            user=user, status=WalletTransaction.Status.COMPLETED
        ).aggregate(total=Sum("delta"))["total"]
        or ZERO
    )
    stored = wallet.total
    return {
        "user": user,
        "stored_total": stored,
        "ledger_total": ledger_total,
        "difference": stored - ledger_total,
        "balanced": stored == ledger_total,
    }
