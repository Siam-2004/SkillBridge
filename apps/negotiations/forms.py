"""Offer forms for the negotiation room."""

from __future__ import annotations

from django import forms
from django.utils import timezone


class OfferForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1, decimal_places=2, label="Amount (SkillCoin)"
    )
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    deliverables = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="One per line. These become the agreement's deliverables.",
    )
    revision_limit = forms.IntegerField(min_value=0, max_value=10, initial=2)
    requirements = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text="Anything else that forms part of the deal.",
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Note to the other party",
    )
    is_final = forms.BooleanField(
        required=False,
        label="Mark this as my final offer",
    )

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline <= timezone.now():
            raise forms.ValidationError("The deadline must be in the future.")
        return deadline