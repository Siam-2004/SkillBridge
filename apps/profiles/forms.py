"""Profile forms."""

from __future__ import annotations

from django import forms

from apps.profiles.models import (
    Category,
    ClientProfile,
    Education,
    Experience,
    FreelancerProfile,
    Skill,
)


class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = [
            "profile_picture",
            "company_name",
            "company_description",
            "industry",
            "bio",
            "phone",
            "location",
            "website",
        ]
        widgets = {
            "company_description": forms.Textarea(attrs={"rows": 4}),
            "bio": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "bio": "What you hire for, and what a freelancer should know before proposing.",
        }


class FreelancerProfileForm(forms.ModelForm):
    class Meta:
        model = FreelancerProfile
        fields = [
            "profile_picture",
            "professional_title",
            "bio",
            "location",
            "hourly_rate",
            "availability",
            "experience_level",
            "years_experience",
            "website",
            "github_url",
            "linkedin_url",
            "languages",
            "is_available_for_hire",
        ]
        widgets = {"bio": forms.Textarea(attrs={"rows": 5})}
        labels = {"is_available_for_hire": "Show me in the freelancer directory"}
        help_texts = {
            "hourly_rate": "Indicative only — every engagement is priced in the agreement.",
        }


class SkillSelectionForm(forms.Form):
    """Skills with a self-rated level, submitted as one set."""

    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(is_active=True).order_by("name"),
        widget=forms.SelectMultiple(attrs={"size": 12}),
        required=False,
        help_text="Hold Ctrl (or Cmd) to select several.",
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.filter(is_active=True).order_by("name"),
        widget=forms.SelectMultiple(attrs={"size": 6}),
        required=False,
    )


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = [
            "position",
            "company",
            "location",
            "employment_type",
            "description",
            "start_date",
            "end_date",
            "is_current",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The end date cannot be before the start date.")
        if not cleaned.get("is_current") and not end:
            self.add_error("end_date", "Give an end date, or tick “current”.")
        return cleaned


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = [
            "institution",
            "degree",
            "field",
            "grade",
            "description",
            "start_date",
            "end_date",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class FreelancerFilterForm(forms.Form):
    """The directory filter panel. Every field the specification lists."""

    SORTS = [
        ("rating", "Highest rated"),
        ("reviews", "Most reviewed"),
        ("projects", "Most projects"),
        ("rate_low", "Lowest rate"),
        ("rate_high", "Highest rate"),
        ("newest", "Newest"),
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
    min_rating = forms.DecimalField(
        required=False, min_value=0, max_value=5, label="Minimum rating"
    )
    min_reviews = forms.IntegerField(
        required=False, min_value=0, label="Minimum reviews"
    )
    min_projects = forms.IntegerField(
        required=False, min_value=0, label="Completed projects"
    )
    availability = forms.ChoiceField(required=False, choices=[("", "Any availability")])
    experience_level = forms.ChoiceField(
        required=False, choices=[("", "Any experience")]
    )
    min_rate = forms.DecimalField(required=False, min_value=0, label="Rate from")
    max_rate = forms.DecimalField(required=False, min_value=0, label="Rate to")
    professional_title = forms.CharField(required=False, label="Title contains")
    has_portfolio = forms.ChoiceField(
        required=False,
        choices=[("", "Any"), ("yes", "Has a portfolio")],
        label="Portfolio",
    )
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["availability"].choices += list(
            FreelancerProfile.Availability.choices
        )
        self.fields["experience_level"].choices += list(
            FreelancerProfile.ExperienceLevel.choices
        )
