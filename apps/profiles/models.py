"""Client and freelancer profiles."""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel
from apps.core.money import ZERO, MoneyField


# --------------------------------------------------------------------------- #
# Taxonomy — what people do, and what jobs ask for
# --------------------------------------------------------------------------- #
class Category(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=40, blank=True, help_text="Icon key used by the templates."
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "name")
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)


class Skill(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    # Denormalised popularity, refreshed by ``manage.py recompute_metrics``.
    # Orders the skill picker and surfaces trending skills on the home page.
    usage_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ("-usage_count", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)


class ClientProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_profile",
    )
    profile_picture = models.ImageField(
        upload_to="profiles/client/%Y/%m/", null=True, blank=True
    )
    bio = models.TextField(blank=True, max_length=2000)
    company_name = models.CharField(max_length=160, blank=True)
    company_description = models.TextField(blank=True, max_length=2000)
    company_size = models.CharField(max_length=40, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=160, blank=True)
    website = models.URLField(blank=True)

    # Denormalised public metrics.  Recomputed by services whenever the
    # underlying event happens, so a profile page is a single row read.
    jobs_posted = models.PositiveIntegerField(default=0)
    active_projects = models.PositiveIntegerField(default=0)
    completed_projects = models.PositiveIntegerField(default=0)
    total_hired = models.PositiveIntegerField(default=0)
    total_spent = MoneyField()

    is_profile_complete = models.BooleanField(default=False)
    search_text = models.TextField(blank=True, editable=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["search_text"], name="clientprofile_search_text")
        ]

    def __str__(self) -> str:
        return f"client<{self.user_id}>"

    @property
    def display_name(self) -> str:
        return self.company_name or self.user.full_name

    @property
    def completeness(self) -> int:
        """Percent complete — drives the "finish your profile" nudge."""
        fields = [
            self.bio,
            self.company_name,
            self.location,
            self.phone,
            bool(self.user.avatar),
            self.user.first_name,
        ]
        return int(sum(1 for f in fields if f) / len(fields) * 100)

    def get_absolute_url(self) -> str:
        return reverse("clients:client_public", args=[self.user.username])


class FreelancerProfile(TimeStampedModel):
    class Availability(models.TextChoices):
        FULL_TIME = "FULL_TIME", "Available full time"
        PART_TIME = "PART_TIME", "Available part time"
        LIMITED = "LIMITED", "Limited availability"
        UNAVAILABLE = "UNAVAILABLE", "Not available"

    class ExperienceLevel(models.TextChoices):
        ENTRY = "ENTRY", "Entry level"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        EXPERT = "EXPERT", "Expert"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="freelancer_profile",
    )
    profile_picture = models.ImageField(
        upload_to="profiles/freelancer/%Y/%m/", null=True, blank=True
    )
    professional_title = models.CharField(max_length=160, blank=True)
    bio = models.TextField(blank=True, max_length=3000)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=160, blank=True)
    website = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    skills = models.ManyToManyField(
        "profiles.Skill",
        through="FreelancerSkill",
        related_name="freelancers",
        blank=True,
    )
    categories = models.ManyToManyField(
        "profiles.Category", related_name="freelancers", blank=True
    )

    hourly_rate = MoneyField(help_text="Indicative rate in SkillCoin per hour.")
    availability = models.CharField(
        max_length=12,
        choices=Availability.choices,
        default=Availability.FULL_TIME,
        db_index=True,
    )
    experience_level = models.CharField(
        max_length=12,
        choices=ExperienceLevel.choices,
        default=ExperienceLevel.INTERMEDIATE,
        db_index=True,
    )
    years_experience = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(60)]
    )
    languages = models.CharField(max_length=200, blank=True)

    # Denormalised public metrics.
    completed_projects = models.PositiveIntegerField(default=0, db_index=True)
    active_projects = models.PositiveIntegerField(default=0)
    total_earned = MoneyField()
    proposals_submitted = models.PositiveIntegerField(default=0)
    proposals_accepted = models.PositiveIntegerField(default=0)
    on_time_deliveries = models.PositiveIntegerField(default=0)
    late_deliveries = models.PositiveIntegerField(default=0)

    is_profile_complete = models.BooleanField(default=False, db_index=True)
    is_available_for_hire = models.BooleanField(default=True, db_index=True)
    search_text = models.TextField(blank=True, editable=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["search_text"], name="freelancerprofile_search_text"),
            models.Index(fields=["availability", "is_available_for_hire"]),
            models.Index(fields=["-completed_projects"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(hourly_rate__gte=ZERO),
                name="freelancer_rate_non_negative",
            )
        ]

    def __str__(self) -> str:
        return f"freelancer<{self.user_id}>"

    @property
    def display_title(self) -> str:
        return self.professional_title or "Freelancer"

    @property
    def success_rate(self) -> int:
        """Accepted proposals as a percentage of submitted ones."""
        if not self.proposals_submitted:
            return 0
        return round(self.proposals_accepted / self.proposals_submitted * 100)

    @property
    def on_time_rate(self) -> int:
        total = self.on_time_deliveries + self.late_deliveries
        if not total:
            return 0
        return round(self.on_time_deliveries / total * 100)

    @property
    def completeness(self) -> int:
        fields = [
            self.professional_title,
            self.bio,
            self.location,
            self.hourly_rate > ZERO,
            bool(self.user.avatar),
            self.skills.exists(),
            self.experiences.exists(),
            self.user.first_name,
        ]
        return int(sum(1 for f in fields if f) / len(fields) * 100)

    def get_absolute_url(self) -> str:
        return reverse("directory:freelancer_public", args=[self.user.username])


class FreelancerSkill(TimeStampedModel):
    """A skill claim with a self-rated proficiency.

    Kept as a through model rather than a plain M2M so search can rank an
    "expert in Django" above someone who listed it as a beginner.
    """

    class Level(models.IntegerChoices):
        BEGINNER = 1, "Beginner"
        INTERMEDIATE = 2, "Intermediate"
        ADVANCED = 3, "Advanced"
        EXPERT = 4, "Expert"

    profile = models.ForeignKey(
        FreelancerProfile, on_delete=models.CASCADE, related_name="skill_entries"
    )
    skill = models.ForeignKey(
        "profiles.Skill", on_delete=models.CASCADE, related_name="freelancer_entries"
    )
    level = models.PositiveSmallIntegerField(
        choices=Level.choices, default=Level.INTERMEDIATE
    )
    years = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(60)]
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_primary", "-level", "skill__name")
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "skill"], name="freelancerskill_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.skill_id}@{self.get_level_display()}"


class Experience(TimeStampedModel):
    profile = models.ForeignKey(
        FreelancerProfile, on_delete=models.CASCADE, related_name="experiences"
    )
    position = models.CharField(max_length=160)
    company = models.CharField(max_length=160)
    location = models.CharField(max_length=160, blank=True)
    employment_type = models.CharField(max_length=60, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ("-is_current", "-start_date")

    def __str__(self) -> str:
        return f"{self.position} @ {self.company}"


class Education(TimeStampedModel):
    profile = models.ForeignKey(
        FreelancerProfile, on_delete=models.CASCADE, related_name="education"
    )
    institution = models.CharField(max_length=180)
    degree = models.CharField(max_length=160)
    field = models.CharField(max_length=160, blank=True, verbose_name="field of study")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    grade = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True, max_length=1000)

    class Meta:
        ordering = ("-end_date", "-start_date")
        verbose_name_plural = "education"

    def __str__(self) -> str:
        return f"{self.degree}, {self.institution}"
