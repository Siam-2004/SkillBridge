"""Portfolio forms."""

from __future__ import annotations

from django import forms

from apps.portfolios.models import Portfolio
from apps.profiles.models import Category, Skill


class PortfolioForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )

    class Meta:
        model = Portfolio
        fields = [
            "title",
            "description",
            "cover_image",
            "demo_url",
            "repository_url",
            "technologies",
            "tech_stack",
            "category",
            "role",
            "responsibilities",
            "duration_months",
            "outcome",
            "tags",
            "client_name",
            "completed_on",
            "is_public",
            "confidentiality_note",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "responsibilities": forms.Textarea(attrs={"rows": 3}),
            "outcome": forms.Textarea(attrs={"rows": 3}),
            "completed_on": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {
            "technologies": "Comma-separated.",
            "is_public": "Only tick this if you are free to show the work.",
            "confidentiality_note": (
                "If any part of the work is confidential, say so here and keep "
                "the entry private."
            ),
            "client_name": "Leave blank if you may not name the client.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        # A confidential entry cannot also be public: that is the whole point
        # of recording the note.
        if (
            cleaned.get("is_public")
            and (cleaned.get("confidentiality_note") or "").strip()
        ):
            self.add_error(
                "is_public",
                "This entry is marked confidential, so it cannot be public. "
                "Clear the confidentiality note first.",
            )
        return cleaned


class PortfolioMediaForm(forms.Form):
    image = forms.ImageField(label="Screenshot")
    caption = forms.CharField(max_length=200, required=False)
    alt_text = forms.CharField(
        max_length=200,
        required=False,
        label="Alt text",
        help_text="Describe the image for anyone using a screen reader.",
    )
