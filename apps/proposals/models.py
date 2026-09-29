
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField


class ProposalQuerySet(models.QuerySet):
    def open_proposals(self):
        return self.filter(status__in=Proposal.OPEN_STATUSES)

    def for_freelancer(self, freelancer):
        return self.filter(freelancer=freelancer)

    def for_job(self, job):
        return self.filter(job=job)


class Proposal(BaseModel):
    """A proposal submitted by a freelancer for a posted job."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        NEGOTIATING = "NEGOTIATING", "Negotiating"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    OPEN_STATUSES = [
        Status.SUBMITTED,
        Status.UNDER_REVIEW,
        Status.NEGOTIATING,
    ]

    job = models.ForeignKey(
        "marketplace.Job", on_delete=models.CASCADE, related_name="proposals"
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposals"
    )

    cover_letter = models.TextField(
        max_length=5000,
        help_text="Explain your approach, relevant experience, and why you are the best fit.",
    )
    proposed_amount = MoneyField(
        help_text="Proposed budget in SkillCoin."
    )
    estimated_days = models.PositiveSmallIntegerField(
        default=7,
        help_text="Estimated working days to complete the job."
    )
    deliverables = models.TextField(
        blank=True,
        max_length=3000,
        help_text="List of deliverables or milestones proposed, one per line.",
    )
    revision_limit = models.PositiveSmallIntegerField(
        default=2,
        help_text="Number of free review/revision rounds included."
    )
    additional_message = models.TextField(
        blank=True,
        max_length=2000,
        help_text="Optional note regarding availability, calls, or prerequisites."
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )
    rejection_reason = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    objects = ProposalQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["job", "status"]),
            models.Index(fields=["freelancer", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(proposed_amount__gt=ZERO),
                name="proposal_amount_positive",
            ),
            models.CheckConstraint(
                check=models.Q(estimated_days__gte=1),
                name="proposal_estimated_days_positive",
            ),
            # Duplicate-proposal protection: At most one active proposal per (job, freelancer).
            models.UniqueConstraint(
                fields=["job", "freelancer"],
                condition=~models.Q(status="WITHDRAWN"),
                name="unique_active_proposal_per_job",
            ),
        ]

    def __str__(self) -> str:
        return f"Proposal<{self.public_id}> by {self.freelancer} on {self.job.title}"

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    @property
    def can_withdraw(self) -> bool:
        return self.status in (self.Status.SUBMITTED, self.Status.UNDER_REVIEW)

    @property
    def deliverable_list(self) -> list[str]:
        return [d.strip(" -•") for d in self.deliverables.splitlines() if d.strip()]

    def get_absolute_url(self) -> str:
        return reverse("proposals:detail", args=[self.public_id])


class ProposalAttachment(TimeStampedModel):
    """Spec or sample work attached to a proposal."""

    proposal = models.ForeignKey(
        Proposal, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="proposals/%Y/%m/")
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.original_name
