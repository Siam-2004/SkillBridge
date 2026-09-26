"""Read paths for wallet, ledger and finance screens."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.money import ZERO
from apps.wallets.models import Deposit, Wallet, WalletTransaction, Withdrawal


def get_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def wallet_summary(user) -> dict:
    wallet = get_wallet(user)
    pending_dep = Deposit.objects.filter(
        user=user, status=Deposit.Status.PENDING
    ).aggregate(n=Count("id"), total=Sum("amount"))
    pending_wdr = Withdrawal.objects.filter(
        user=user, status=Withdrawal.Status.PENDING
    ).aggregate(n=Count("id"), total=Sum("amount"))
    return {
        "wallet": wallet,
        "available": wallet.available_balance,
        "reserved": wallet.reserved_balance,
        "escrow": wallet.escrow_balance,
        "total": wallet.total,
        "lifetime_deposited": wallet.lifetime_deposited,
        "lifetime_withdrawn": wallet.lifetime_withdrawn,
        "lifetime_earned": wallet.lifetime_earned,
        "lifetime_spent": wallet.lifetime_spent,
        "pending_deposits": {
            "n": pending_dep["n"] or 0,
            "total": pending_dep["total"] or ZERO,
        },
        "pending_withdrawals": {
            "n": pending_wdr["n"] or 0,
            "total": pending_wdr["total"] or ZERO,
        },
    }


def transactions_for(
    user, *, transaction_type: str = "", direction: str = "", search: str = ""
):
    """The user-facing ledger view."""
    qs = (
        WalletTransaction.objects.filter(user=user)
        .select_related("counterparty")
        .order_by("-created_at", "-id")
    )
    if transaction_type:
        qs = qs.filter(transaction_type=transaction_type)
    if direction == "in":
        qs = qs.filter(delta__gt=ZERO)
    elif direction == "out":
        qs = qs.filter(delta__lt=ZERO)
    elif direction == "internal":
        qs = qs.filter(delta=ZERO)
    if search:
        qs = qs.filter(
            Q(internal_transaction_id__icontains=search)
            | Q(description__icontains=search)
        )
    return qs


def deposits_for(user, *, status: str = ""):
    qs = Deposit.objects.filter(user=user).order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    return qs


def withdrawals_for(user, *, status: str = ""):
    qs = Withdrawal.objects.filter(user=user).order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    return qs


def earnings_breakdown(user) -> dict:
    """Freelancer earnings widget."""
    rows = WalletTransaction.objects.filter(
        user=user,
        transaction_type=WalletTransaction.Type.PROJECT_PAYMENT,
        status=WalletTransaction.Status.COMPLETED,
    )
    return {
        "total": rows.aggregate(t=Sum("amount"))["t"] or ZERO,
        "count": rows.count(),
        "by_project": list(
            rows.values("project_id")
            .annotate(total=Sum("amount"), payments=Count("id"))
            .order_by("-total")[:10]
        ),
    }


# --------------------------------------------------------------------------- #
# Administrator finance views
# --------------------------------------------------------------------------- #
def finance_overview() -> dict:
    """The headline numbers for the administrator finance view."""
    wallets = Wallet.objects.aggregate(
        available=Sum("available_balance"),
        reserved=Sum("reserved_balance"),
        escrow=Sum("escrow_balance"),
    )
    return {
        "total_deposits": ZERO,
        "pending_deposits": ZERO,
        "pending_deposit_count": 0,
        "total_withdrawals": ZERO,
        "open_withdrawals": ZERO,
        "open_withdrawal_count": 0,
        "active_escrow": ZERO,
        "escrow_funded": ZERO,
        "released_payments": ZERO,
        "released_count": 0,
        "auto_released": ZERO,
        "auto_released_count": 0,
        "refunds": ZERO,
        "disputed_funds": ZERO,
        "wallet_available": wallets["available"] or ZERO,
        "wallet_reserved": wallets["reserved"] or ZERO,
        "wallet_escrow": wallets["escrow"] or ZERO,
        "float_total": (wallets["available"] or ZERO)
        + (wallets["reserved"] or ZERO)
        + (wallets["escrow"] or ZERO),
    }


def ledger_search(
    *,
    query: str = "",
    transaction_type: str = "",
    status: str = "",
    date_from=None,
    date_to=None,
    min_amount=None,
    max_amount=None,
):
    """One searchable ledger across every identifier an operator has."""
    qs = WalletTransaction.objects.select_related(
        "user", "counterparty", "actor"
    )
    if query:
        query = query.strip()
        qs = qs.filter(
            Q(internal_transaction_id__iexact=query)
            | Q(internal_transaction_id__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__username__icontains=query)
            | Q(description__icontains=query)
        )
        if transaction_type:
            qs = qs.filter(transaction_type=transaction_type)
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)
    if min_amount not in (None, ""):
        qs = qs.filter(amount__gte=min_amount)
    if max_amount not in (None, ""):
        qs = qs.filter(amount__lte=max_amount)
    return qs.order_by("-created_at", "-id")


def daily_series(days: int = 30) -> list[dict]:
    """Deposit, payout and escrow totals per day."""
    from django.db.models.functions import TruncDate

    since = timezone.now() - timedelta(days=days)
    rows = (
        WalletTransaction.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            deposits=Sum(
                "amount", filter=Q(transaction_type=WalletTransaction.Type.DEPOSIT)
            ),
            payouts=Sum(
                "amount", filter=Q(transaction_type=WalletTransaction.Type.WITHDRAWAL)
            ),
            escrowed=Sum(
                "amount", filter=Q(transaction_type=WalletTransaction.Type.ESCROW_HOLD)
            ),
            released=Sum(
                "amount",
                filter=Q(transaction_type=WalletTransaction.Type.PROJECT_PAYMENT),
            ),
        )
        .order_by("day")
    )
    return [
        {
            "day": row["day"].isoformat(),
            "deposits": float(row["deposits"] or 0),
            "payouts": float(row["payouts"] or 0),
            "escrowed": float(row["escrowed"] or 0),
            "released": float(row["released"] or 0),
        }
        for row in rows
    ]
