"""Job forms.

The forms shape and sanity-check input. Whether a job *may* be published — the
budget rule — is decided in ``marketplace.services``, because that check has to
hold for the seed command and the tests as well as for this form.
"""
from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.marketplace.models import Job
from apps.profiles.models import Category, Skill


class JobForm(forms.ModelForm):
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 10}),
        help_text="Hold Ctrl (or Cmd) to select several.",
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "category",
            "description",
            "requirements",
            "budget",
            "deadline",
            "job_type",
            "complexity",
            "experience_level",
            "estimated_days",
            "people_required",
            "team_required",
        ]
        widgets = {
            "budget": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Enter any budget amount (e.g. 50, 100, 250)",
                }
            ),
            "description": forms.Textarea(attrs={"rows": 7}),
            "requirements": forms.Textarea(
                attrs={"rows": 5, "placeholder": "One deliverable per line."}
            ),
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        help_texts = {
            "budget": (
                "The full amount is reserved from your available balance the "
                "moment the job is published, and stays reserved until you "
                "cancel or fund an agreement."
            ),
            "requirements": "What must be delivered. One per line.",
            "team_required": "Allow the hired freelancer to build a team for this job.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["deadline"].required = True

    def clean_budget(self):
        from apps.core.money import ZERO
        budget = self.cleaned_data.get("budget")
        if budget is None or budget <= ZERO:
            raise forms.ValidationError("Budget must be greater than zero.")
        return budget

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        if deadline and deadline <= timezone.now():
            raise forms.ValidationError("The deadline must be in the future.")
        return deadline

    def clean_people_required(self):
        people = self.cleaned_data.get("people_required") or 1
        if people < 1:
            raise forms.ValidationError("At least one freelancer is required.")
        return people


class JobFilterForm(forms.Form):
    """Every filter and sort order the specification lists for job search."""

    SORTS = [
        ("newest", "Newest first"),
        ("oldest", "Oldest first"),
        ("budget_high", "Highest budget"),
        ("budget_low", "Lowest budget"),
        ("deadline", "Closest deadline"),
        ("proposals", "Most proposals"),
        ("least_proposals", "Fewest proposals"),
    ]

    q = forms.CharField(required=False, label="Keyword")
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="Any category",
    )
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True), required=False
    )
    min_budget = forms.DecimalField(required=False, min_value=0, label="Budget from")
    max_budget = forms.DecimalField(required=False, min_value=0, label="Budget to")
    deadline_before = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Deadline before",
    )
    experience_level = forms.ChoiceField(
        required=False, choices=[("", "Any experience")]
    )
    job_type = forms.ChoiceField(required=False, choices=[("", "Any type")])
    complexity = forms.ChoiceField(required=False, choices=[("", "Any complexity")])
    people = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any size"),
            ("single", "One freelancer"),
            ("multiple", "Several freelancers"),
        ],
        label="Freelancers needed",
    )
    team_required = forms.ChoiceField(
        required=False,
        choices=[("", "Any"), ("yes", "Team allowed"), ("no", "Solo only")],
        label="Team",
    )
    status = forms.ChoiceField(required=False, choices=[("", "Any status")])
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["experience_level"].choices += list(Job.Experience.choices)
        self.fields["job_type"].choices += list(Job.JobType.choices)
        self.fields["complexity"].choices += list(Job.Complexity.choices)
        self.fields["status"].choices += [
            (s, dict(Job.Status.choices)[s]) for s in Job.OPEN_STATUSES
        ]

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("min_budget"), cleaned.get("max_budget")
        if low is not None and high is not None and low > high:
            self.add_error(
                "max_budget", "The upper budget must be at least the lower one."
            )
        return cleaned


class CancelJobForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Shown to anyone who has already proposed.",
    )
