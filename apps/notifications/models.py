"""In-app notifications."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from apps.core.models import BaseModel, TimeStampedModel


class NotificationType(models.TextChoices):
    NEW_PROPOSAL = "NEW_PROPOSAL", "New proposal"
    PROPOSAL_ACCEPTED = "PROPOSAL_ACCEPTED", "Proposal accepted"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED", "Proposal rejected"
    NEW_MESSAGE = "NEW_MESSAGE", "New message"
    MENTION = "MENTION", "You were mentioned"
    NEW_OFFER = "NEW_OFFER", "New offer"
    COUNTER_OFFER = "COUNTER_OFFER", "Counter offer"
    OFFER_EXPIRED = "OFFER_EXPIRED", "Offer expired"
    AGREEMENT_ACCEPTED = "AGREEMENT_ACCEPTED", "Agreement accepted"
    AGREEMENT_MODIFICATION = "AGREEMENT_MODIFICATION", "Agreement modification request"
    TEAM_INVITATION = "TEAM_INVITATION", "Team invitation"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED", "Invitation accepted"
    INVITATION_DECLINED = "INVITATION_DECLINED", "Invitation declined"
    TASK_ASSIGNED = "TASK_ASSIGNED", "Task assigned"
    WORK_SUBMITTED = "WORK_SUBMITTED", "Work submitted"
    REVISION_REQUESTED = "REVISION_REQUESTED", "Revision requested"
    TASK_APPROVED = "TASK_APPROVED", "Task approved"
    DEPOSIT_APPROVED = "DEPOSIT_APPROVED", "Deposit approved"
    DEPOSIT_REJECTED = "DEPOSIT_REJECTED", "Deposit rejected"
    ESCROW_FUNDED = "ESCROW_FUNDED", "Escrow funded"
    PAYMENT_RELEASED = "PAYMENT_RELEASED", "Payment released"
    PAYMENT_WINDOW_OPENED = "PAYMENT_WINDOW_OPENED", "Review window opened"
    PAYMENT_WINDOW_CLOSING = "PAYMENT_WINDOW_CLOSING", "Review window closing"
    WITHDRAWAL_UPDATE = "WITHDRAWAL_UPDATE", "Withdrawal update"
    REVIEW_RECEIVED = "REVIEW_RECEIVED", "Review received"
    DISPUTE_CREATED = "DISPUTE_CREATED", "Dispute created"
    DISPUTE_RESOLVED = "DISPUTE_RESOLVED", "Dispute resolved"
    DEADLINE_APPROACHING = "DEADLINE_APPROACHING", "Deadline approaching"
    PROJECT_READY_FOR_REVIEW = "PROJECT_READY_FOR_REVIEW", "Project ready for review"
    PROJECT_COMPLETED = "PROJECT_COMPLETED", "Project completed"
    JOB_CANCELLED = "JOB_CANCELLED", "Job cancelled"
    ACCOUNT_NOTICE = "ACCOUNT_NOTICE", "Account notice"


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True)

    def for_user(self, user):
        return self.filter(recipient=user)


class Notification(BaseModel):
    class Level(models.TextChoices):
        INFO = "INFO", "Info"
        SUCCESS = "SUCCESS", "Success"
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications_sent")
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices, db_index=True)
    level = models.CharField(max_length=8, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500, blank=True)
    # Absolute URL, because a notification raised by the freelancer portal may
    # need to deep-link into the client portal or back to the public site.
    target_url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"]),
            models.Index(fields=["recipient", "notification_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_type} → {self.recipient_id}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationPreference(TimeStampedModel):
    """Per-user delivery choices.

    Money and dispute notifications are deliberately *not* switchable — a user
    must not be able to opt out of being told that their funds moved.
    """

    ALWAYS_EMAIL = {
        NotificationType.DEPOSIT_APPROVED,
        NotificationType.DEPOSIT_REJECTED,
        NotificationType.PAYMENT_RELEASED,
        NotificationType.WITHDRAWAL_UPDATE,
        NotificationType.DISPUTE_CREATED,
        NotificationType.DISPUTE_RESOLVED,
        NotificationType.TEAM_INVITATION,
        NotificationType.ACCOUNT_NOTICE,
    }
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference")
    email_messages = models.BooleanField(default=True)
    email_proposals = models.BooleanField(default=True)
    email_tasks = models.BooleanField(default=True)
    email_deadlines = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)

    def allows_email(self, kind: str) -> bool:
        if kind in self.ALWAYS_EMAIL:
            return True
        mapping = {
            NotificationType.NEW_MESSAGE: self.email_messages,
            NotificationType.MENTION: self.email_messages,
            NotificationType.NEW_PROPOSAL: self.email_proposals,
            NotificationType.NEW_OFFER: self.email_proposals,
            NotificationType.COUNTER_OFFER: self.email_proposals,
            NotificationType.TASK_ASSIGNED: self.email_tasks,
            NotificationType.WORK_SUBMITTED: self.email_tasks,
            NotificationType.REVISION_REQUESTED: self.email_tasks,
            NotificationType.DEADLINE_APPROACHING: self.email_deadlines,
            NotificationType.PAYMENT_WINDOW_CLOSING: self.email_deadlines,
        }
        return mapping.get(kind, False)