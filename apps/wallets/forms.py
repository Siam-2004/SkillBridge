"""Wallet filters."""

from __future__ import annotations

from django import forms

from apps.wallets.models import Deposit, WalletTransaction, Withdrawal


class TransactionFilterForm(forms.Form):
    transaction_type = forms.ChoiceField(
        required=False, choices=[("", "All types")], label="Type"
    )
    direction = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All movements"),
            ("in", "Money in"),
            ("out", "Money out"),
            ("internal", "Between my own buckets"),
        ],
    )
    q = forms.CharField(required=False, label="Search")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["transaction_type"].choices += list(WalletTransaction.Type.choices)


class DepositForm(forms.Form):
    amount = forms.DecimalField(
        min_value=50,
        max_value=1000000,
        decimal_places=2,
        label="Deposit Amount (SkillCoin / BDT)",
        widget=forms.NumberInput(
            attrs={"placeholder": "e.g. 1000", "min": "50", "step": "50", "autofocus": "autofocus"}
        ),
    )
    payment_method = forms.ChoiceField(
        choices=Deposit.Method.choices,
        label="Payment Method",
        initial=Deposit.Method.BKASH,
    )
    sender_number = forms.CharField(
        max_length=30,
        label="Sender Phone / Account Number",
        widget=forms.TextInput(attrs={"placeholder": "01XXXXXXXXX or Account No."}),
        help_text="The number you used to send the money.",
    )
    transaction_id = forms.CharField(
        max_length=100,
        label="Transaction ID (TrxID)",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 9J56K8P1"}),
        help_text="Transaction reference number provided by your payment provider.",
    )

    def clean(self):
        cleaned = super().clean()
        sender = cleaned.get("sender_number")
        trx = cleaned.get("transaction_id")
        if not sender:
            self.add_error("sender_number", "Sender phone / account number is required.")
        if not trx:
            self.add_error("transaction_id", "Transaction ID is required.")
        return cleaned


class WithdrawalForm(forms.Form):
    amount = forms.DecimalField(
        min_value=50,
        max_value=500000,
        decimal_places=2,
        label="Withdrawal Amount (SkillCoin / BDT)",
        widget=forms.NumberInput(
            attrs={"placeholder": "e.g. 500", "min": "50", "step": "50", "autofocus": "autofocus"}
        ),
    )
    payment_method = forms.ChoiceField(
        choices=Withdrawal.Method.choices,
        label="Payout Method",
        initial=Withdrawal.Method.BKASH,
    )
    account_number = forms.CharField(
        max_length=50,
        label="Account / Phone Number",
        widget=forms.TextInput(attrs={"placeholder": "01XXXXXXXXX or Bank Account No."}),
    )
    account_name = forms.CharField(
        max_length=100,
        required=False,
        label="Account Holder Name",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Account Holder Name"}),
    )

    def __init__(self, *args, wallet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.wallet = wallet

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.wallet and amount > self.wallet.available_balance:
            raise forms.ValidationError(
                f"Insufficient funds. Your available balance is {self.wallet.available_balance} SkillCoin."
            )
        return amount

