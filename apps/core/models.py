"""Base model classes, site configuration and the activity stream."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# --------------------------------------------------------------------------- #
# Abstract bases
# --------------------------------------------------------------------------- #
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(
        default=timezone.now, db_index=True, editable=False
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Public-facing identifier.

    Rows keep their integer primary key for joins, but anything that appears in
    a URL or an email uses ``public_id`` so that row counts and creation order
    are not leaked to anyone who can read a link.
    """

    public_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Soft-delete. Overridden deliberately: see ``SoftDeleteModel``."""
        return self.update(deleted_at=timezone.now())


class SoftDeleteModel(models.Model):
    """Nothing that could ever be evidence is hard-deleted.

    Chats, submissions, agreements and financial records have to survive for
    dispute resolution and audit, so "delete" means "hide from the active UI".
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, *, save: bool = True):
        self.deleted_at = timezone.now()
        if save:
            self.save(update_fields=["deleted_at", "updated_at"])


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


# --------------------------------------------------------------------------- #
# Site configuration
# --------------------------------------------------------------------------- #
class SiteSetting(TimeStampedModel):
    """Admin-editable runtime configuration.

    Only values an operator may legitimately change while the site is running
    belong here. Financial invariants stay in code and database constraints,
    where an admin cannot reach them.
    """

    class Kind(models.TextChoices):
        STRING = "STRING", "String"
        INTEGER = "INTEGER", "Integer"
        DECIMAL = "DECIMAL", "Decimal"
        BOOLEAN = "BOOLEAN", "Boolean"
        TEXT = "TEXT", "Long text"

    key = models.SlugField(max_length=120, unique=True)
    value = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.STRING)
    group = models.CharField(max_length=60, default="general", db_index=True)
    label = models.CharField(max_length=160)
    help_text = models.CharField(max_length=300, blank=True)
    is_public = models.BooleanField(
        default=False, help_text="Readable from templates without signing in."
    )

    class Meta:
        ordering = ("group", "key")

    def __str__(self) -> str:
        return self.key

    @property
    def typed_value(self):
        raw = (self.value or "").strip()
        if self.kind == self.Kind.INTEGER:
            return int(raw or 0)
        if self.kind == self.Kind.DECIMAL:
            from decimal import Decimal

            return Decimal(raw or "0")
        if self.kind == self.Kind.BOOLEAN:
            return raw.lower() in {"1", "true", "yes", "on"}
        return raw


class HomepageSection(TimeStampedModel):
    """Editable marketing copy for the public home page.

    The *statistics* on the home page are never stored here — they must always
    be computed live, so they live in ``apps.core.selectors.platform_stats``.
    """

    class Slot(models.TextChoices):
        HERO = "HERO", "Hero"
        CLIENT_VALUE = "CLIENT_VALUE", "For clients"
        FREELANCER_VALUE = "FREELANCER_VALUE", "For freelancers"
        HOW_IT_WORKS = "HOW_IT_WORKS", "How it works"
        TRUST = "TRUST", "Trust and safety"
        CTA = "CTA", "Closing call to action"

    slot = models.CharField(max_length=24, choices=Slot.choices, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=400, blank=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="homepage/", blank=True, null=True)
    icon = models.CharField(max_length=40, blank=True)
    button_text = models.CharField(max_length=60, blank=True)
    button_url = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("slot", "sort_order")

    def __str__(self) -> str:
        return f"{self.get_slot_display()} — {self.title or self.pk}"


# --------------------------------------------------------------------------- #
# Activity stream
# --------------------------------------------------------------------------- #
class ActivityVerb(models.TextChoices):
    """Every action that appears in a job's or project's history.

    The specification lists the actions that must be recorded; the extras here
    are the other side of those same events (a rejection as well as an
    approval), because a history that only records success is not a history.
    """

    # Jobs
    JOB_CREATED = "JOB_CREATED", "Job created"
    JOB_PUBLISHED = "JOB_PUBLISHED", "Job published"
    JOB_CANCELLED = "JOB_CANCELLED", "Job cancelled"
    BUDGET_RESERVED = "BUDGET_RESERVED", "Budget reserved"
    BUDGET_RELEASED = "BUDGET_RELEASED", "Budget released"

    # Hiring
    PROPOSAL_SUBMITTED = "PROPOSAL_SUBMITTED", "Proposal submitted"
    PROPOSAL_WITHDRAWN = "PROPOSAL_WITHDRAWN", "Proposal withdrawn"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED", "Proposal rejected"
    NEGOTIATION_OPENED = "NEGOTIATION_OPENED", "Negotiation opened"
    OFFER_CREATED = "OFFER_CREATED", "Offer created"
    COUNTER_OFFER = "COUNTER_OFFER", "Counter offer"
    OFFER_ACCEPTED = "OFFER_ACCEPTED", "Offer accepted"
    OFFER_REJECTED = "OFFER_REJECTED", "Offer rejected"
    AGREEMENT_ACCEPTED = "AGREEMENT_ACCEPTED", "Agreement accepted"
    AGREEMENT_MODIFIED = "AGREEMENT_MODIFIED", "Agreement modified"
    DEADLINE_EXTENDED = "DEADLINE_EXTENDED", "Deadline extended"

    # Money
    DEPOSIT_SUBMITTED = "DEPOSIT_SUBMITTED", "Deposit submitted"
    DEPOSIT_APPROVED = "DEPOSIT_APPROVED", "Deposit approved"
    DEPOSIT_REJECTED = "DEPOSIT_REJECTED", "Deposit rejected"
    ESCROW_FUNDED = "ESCROW_FUNDED", "Escrow funded"
    ALLOCATION_SET = "ALLOCATION_SET", "Task allocation set"
    PAYMENT_RELEASED = "PAYMENT_RELEASED", "Payment released"
    PAYMENT_AUTO_RELEASED = "PAYMENT_AUTO_RELEASED", "Payment auto-released"
    REFUND_ISSUED = "REFUND_ISSUED", "Refund issued"
    WITHDRAWAL_REQUESTED = "WITHDRAWAL_REQUESTED", "Withdrawal requested"
    WITHDRAWAL_COMPLETED = "WITHDRAWAL_COMPLETED", "Withdrawal completed"
    WITHDRAWAL_REJECTED = "WITHDRAWAL_REJECTED", "Withdrawal rejected"

    # Delivery
    PROJECT_CREATED = "PROJECT_CREATED", "Project created"
    PROJECT_READY_FOR_REVIEW = "PROJECT_READY_FOR_REVIEW", "Project ready for review"
    PROJECT_COMPLETED = "PROJECT_COMPLETED", "Project completed"
    PROJECT_CANCELLED = "PROJECT_CANCELLED", "Project cancelled"
    TEAM_CREATED = "TEAM_CREATED", "Team created"
    MEMBER_INVITED = "MEMBER_INVITED", "Member invited"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED", "Invitation accepted"
    INVITATION_DECLINED = "INVITATION_DECLINED", "Invitation declined"
    MEMBER_REMOVED = "MEMBER_REMOVED", "Member removed"
    TASK_CREATED = "TASK_CREATED", "Task created"
    TASK_ASSIGNED = "TASK_ASSIGNED", "Task assigned"
    TASK_STARTED = "TASK_STARTED", "Task started"
    WORK_SUBMITTED = "WORK_SUBMITTED", "Work submitted"
    REVISION_REQUESTED = "REVISION_REQUESTED", "Revision requested"
    TASK_APPROVED = "TASK_APPROVED", "Task approved"
    FILE_UPLOADED = "FILE_UPLOADED", "File uploaded"

    # Communication and trust
    MESSAGE_SENT = "MESSAGE_SENT", "Message sent"
    CONVERSATION_ARCHIVED = "CONVERSATION_ARCHIVED", "Conversation archived"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED", "Review submitted"
    DISPUTE_CREATED = "DISPUTE_CREATED", "Dispute created"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED", "Dispute resolved"


class ActivityLog(TimeStampedModel):
    """The human-readable story of a job or project.

    Distinct from ``AuditLog``: this is what participants read on the activity
    tab, so it is phrased for people. The audit trail is the forensic record and
    is deliberately a separate table with different retention and access.
    """

    class Visibility(models.TextChoices):
        PARTICIPANTS = "PARTICIPANTS", "Project participants"
        PUBLIC = "PUBLIC", "Anyone"
        ADMIN = "ADMIN", "Administrators only"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    action = models.CharField(
        max_length=40, choices=ActivityVerb.choices, db_index=True
    )
    description = models.CharField(max_length=400)

    object_type = models.CharField(max_length=80, blank=True, db_index=True)
    object_id = models.CharField(max_length=80, blank=True, db_index=True)
    target_url = models.CharField(max_length=400, blank=True)

    job_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    project_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    task_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    visibility = models.CharField(
        max_length=14, choices=Visibility.choices, default=Visibility.PARTICIPANTS
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["project_id", "-created_at"]),
            models.Index(fields=["job_id", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.description[:60]}"
