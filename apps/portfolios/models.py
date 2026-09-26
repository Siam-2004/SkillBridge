"""Freelancer portfolio.

A portfolio item is public marketing material, so the model carries an explicit
``is_public`` flag and a ``confidentiality_note``: forbids publishing
confidential project data, and a freelancer who worked on a private client
system needs a way to describe the work without exposing it.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import BaseModel, TimeStampedModel


class Portfolio(BaseModel):
    """One piece of work a freelancer is willing to show publicly."""

    freelancer = models.ForeignKey(
        "profiles.FreelancerProfile",
        on_delete=models.CASCADE,
        related_name="portfolio_items",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240)
    description = models.TextField(max_length=5000)

    cover_image = models.ImageField(
        upload_to="portfolio/covers/%Y/%m/", null=True, blank=True
    )
    demo_url = models.URLField(blank=True, help_text="Live demo, if there is one.")
    repository_url = models.URLField(
        blank=True, help_text="Source code, where it can be shared."
    )

    technologies = models.CharField(
        max_length=400, blank=True, help_text="Comma-separated technology list."
    )
    tech_stack = models.CharField(max_length=400, blank=True)
    skills = models.ManyToManyField(
        "profiles.Skill", related_name="portfolio_entries", blank=True
    )
    category = models.ForeignKey(
        "profiles.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolio_entries",
    )

    role = models.CharField(
        max_length=160, blank=True, help_text="The freelancer's role."
    )
    responsibilities = models.TextField(blank=True, max_length=2000)
    outcome = models.TextField(
        blank=True, max_length=2000, help_text="Result achieved."
    )

    duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    client_name = models.CharField(
        max_length=160, blank=True, help_text="Leave blank if under NDA."
    )
    tags = models.CharField(max_length=300, blank=True)

    is_public = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    confidentiality_note = models.CharField(
        max_length=300,
        blank=True,
        help_text="Shown instead of client details when work is under NDA.",
    )
    order = models.PositiveSmallIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)

    # Set when an item is generated from a completed Skillbridge project, which
    # is what lets the public profile show a "Verified on Skillbridge" badge.
    source_project_id = models.PositiveIntegerField(null=True, blank=True)

    @property
    def source_project(self):
        return None

    search_text = models.TextField(blank=True, editable=False, db_index=True)

    class Meta:
        ordering = ("order", "-completed_on", "-created_at")
        indexes = [
            models.Index(fields=["search_text"], name="portfolio_search_text"),
            models.Index(fields=["freelancer", "is_public", "order"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:240] or "item"
        super().save(*args, **kwargs)

    @property
    def is_verified(self) -> bool:
        return self.source_project_id is not None

    @property
    def technology_list(self) -> list[str]:
        return [t.strip() for t in self.technologies.split(",") if t.strip()]

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def get_absolute_url(self) -> str:
        return reverse("portfolios:detail", args=[self.public_id])


class PortfolioMedia(TimeStampedModel):
    """Screenshots and additional images for one portfolio entry."""

    class Kind(models.TextChoices):
        SCREENSHOT = "SCREENSHOT", "Screenshot"
        IMAGE = "IMAGE", "Image"
        DIAGRAM = "DIAGRAM", "Diagram"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="media"
    )
    image = models.ImageField(upload_to="portfolio/media/%Y/%m/")
    kind = models.CharField(
        max_length=12, choices=Kind.choices, default=Kind.SCREENSHOT
    )
    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "created_at")
        verbose_name_plural = "portfolio media"

    def __str__(self) -> str:
        return self.caption or f"media<{self.pk}>"


class PortfolioView(models.Model):
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    session_key = models.CharField(max_length=60, blank=True)
    viewed_on = models.DateField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "user", "viewed_on"],
                condition=models.Q(user__isnull=False),
                name="portfolioview_unique_user_day",
            ),
            models.UniqueConstraint(
                fields=["portfolio", "session_key", "viewed_on"],
                condition=models.Q(user__isnull=True),
                name="portfolioview_unique_session_day",
            ),
        ]
