"""The wallet and its ledger.

Read-only: nothing here moves money. Deposits and withdrawals live in
``apps.payments``, and every balance change goes through ``wallets.ledger``.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.core.exceptions import DomainError
from apps.core.permissions import verified_required
from apps.core.views import paginate
from apps.wallets import services
from apps.wallets.forms import DepositForm, TransactionFilterForm, WithdrawalForm
from apps.wallets.models import Deposit, Withdrawal
from apps.wallets.selectors import (
    deposits_for,
    earnings_breakdown,
    get_wallet,
    transactions_for,
    wallet_summary,
    withdrawals_for,
)


@verified_required
def deposit_view(request):
    user = request.user
    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["payment_method"]
            sender = form.cleaned_data["sender_number"]
            trx = form.cleaned_data["transaction_id"]

            try:
                deposit = services.create_deposit(
                    user=user,
                    amount=amount,
                    payment_method=method,
                    sender_number=sender,
                    transaction_id=trx,
                )
                messages.info(
                    request,
                    f"Deposit request for {deposit.amount} SkillCoin submitted (Ref: {deposit.reference_id}). It will be credited once verified by Admin.",
                )
                return redirect("wallets:wallet")
            except DomainError as exc:
                messages.error(request, exc.message)
    else:
        initial_amount = request.GET.get("amount", "1000")
        form = DepositForm(initial={"amount": initial_amount})

    return render(
        request,
        "wallets/deposit.html",
        {
            "form": form,
            "info": wallet_summary(user),
            "nav": "wallet",
            "page_title": "Add Funds",
        },
    )


@verified_required
def withdraw_view(request):
    user = request.user
    wallet_obj = get_wallet(user)
    if wallet_obj.is_frozen:
        messages.error(request, f"Your wallet is frozen: {wallet_obj.frozen_reason or 'contact support'}.")
        return redirect("wallets:wallet")

    if request.method == "POST":
        form = WithdrawalForm(request.POST, wallet=wallet_obj)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["payment_method"]
            account_num = form.cleaned_data["account_number"]
            account_name = form.cleaned_data["account_name"]

            try:
                withdrawal = services.request_withdrawal(
                    user=user,
                    amount=amount,
                    payment_method=method,
                    account_number=account_num,
                    account_name=account_name,
                )
                messages.info(
                    request,
                    f"Withdrawal request for {withdrawal.amount} SkillCoin submitted (Ref: {withdrawal.reference_id}). Funds are safely reserved and will be processed upon Admin verification.",
                )
                return redirect("wallets:wallet")
            except DomainError as exc:
                messages.error(request, exc.message)
    else:
        form = WithdrawalForm(wallet=wallet_obj)

    return render(
        request,
        "wallets/withdraw.html",
        {
            "form": form,
            "wallet": wallet_obj,
            "info": wallet_summary(user),
            "nav": "wallet",
            "page_title": "Withdraw Funds",
        },
    )


@verified_required
def wallet(request):
    user = request.user
    return render(
        request,
        "wallets/wallet.html",
        {
            "info": wallet_summary(user),
            "recent": transactions_for(user)[:12],
            "deposits": deposits_for(user)[:5],
            "withdrawals": withdrawals_for(user)[:5],
            "earnings": earnings_breakdown(user) if user.is_freelancer else None,
            "nav": "wallet",
            "page_title": "Wallet",
        },
    )


@verified_required
def transactions(request):
    """The caller's own ledger. There is no unscoped view of this anywhere."""
    form = TransactionFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}

    rows = transactions_for(
        request.user,
        transaction_type=data.get("transaction_type") or "",
        direction=data.get("direction") or "",
        search=data.get("q") or "",
    )
    page, querystring = paginate(request, rows, 30)
    return render(
        request,
        "wallets/transactions.html",
        {
            "form": form,
            "page": page,
            "querystring": querystring,
            "info": wallet_summary(request.user),
            "nav": "transactions",
            "page_title": "Transactions",
        },
    )
