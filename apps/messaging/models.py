from __future__ import annotations
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.models import BaseModel, TimeStampedModel

class ConversationQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(participants__user=user, participants__left_at__isnull=True)

    def active(self):
        return self.filter(status=Conversation.Status.ACTIVE)

class Conversation(BaseModel):

    class Kind(models.TextChoices):
        JOB = ('JOB_CONVERSATION', 'Job conversation')
        PROJECT = ('PROJECT_CONVERSATION', 'Project conversation')
        DISPUTE = ('DISPUTE_CONVERSATION', 'Dispute conversation')

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        ARCHIVED = ('ARCHIVED', 'Archived')
    conversation_type = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    subject = models.CharField(max_length=200, blank=True)
    job = models.ForeignKey('marketplace.Job', on_delete=models.CASCADE, null=True, blank=True, related_name='conversations')
    agreement = models.ForeignKey('agreements.Agreement', on_delete=models.CASCADE, null=True, blank=True, related_name='conversations')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archive_reason = models.CharField(max_length=200, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_message_preview = models.CharField(max_length=200, blank=True)
    message_count = models.PositiveIntegerField(default=0)
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations_started')
    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ('-last_message_at', '-created_at')
        constraints = [models.UniqueConstraint(fields=['job', 'initiator'], condition=models.Q(conversation_type='JOB_CONVERSATION'), name='conversation_unique_per_job_initiator')]
        indexes = [models.Index(fields=['conversation_type', 'status', '-last_message_at'])]

    def __str__(self) -> str:
        return f'conversation<{self.public_id}> {self.conversation_type}'

    @property
    def is_archived(self) -> bool:
        return self.status == self.Status.ARCHIVED

    @property
    def is_writable(self) -> bool:
        return self.status == self.Status.ACTIVE

    def participant_users(self):
        from apps.accounts.models import User
        return User.objects.filter(conversation_memberships__conversation=self, conversation_memberships__left_at__isnull=True)

    def get_absolute_url(self) -> str:
        return reverse('messaging:detail', args=[self.public_id])

class ConversationParticipant(TimeStampedModel):

    class Role(models.TextChoices):
        CLIENT = ('CLIENT', 'Client')
        FREELANCER = ('FREELANCER', 'Freelancer')
        TEAM_OWNER = ('TEAM_OWNER', 'Team owner')
        TEAM_MEMBER = ('TEAM_MEMBER', 'Team member')
        ADMIN = ('ADMIN', 'Admin')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversation_memberships')
    role = models.CharField(max_length=14, choices=Role.choices)
    last_read_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)
    is_muted = models.BooleanField(default=False)
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation', 'user'], name='conversationparticipant_unique')]
        indexes = [models.Index(fields=['user', '-unread_count'])]

    def __str__(self) -> str:
        return f'{self.user_id}@{self.conversation_id}'

class Message(BaseModel):

    class Kind(models.TextChoices):
        TEXT = ('TEXT', 'Message')
        SYSTEM = ('SYSTEM', 'System event')
        TASK_REF = ('TASK_REF', 'Task reference')
        FILE = ('FILE', 'File')
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages_sent')
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TEXT)
    content = models.TextField(max_length=8000, blank=True)
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='message_mentions')
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    search_text = models.TextField(blank=True, editable=False, db_index=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes = [models.Index(fields=['conversation', 'created_at']), models.Index(fields=['sender', '-created_at']), models.Index(fields=['search_text'], name='message_search_text')]

    def __str__(self) -> str:
        return f'message<{self.public_id}>'

    @property
    def preview(self) -> str:
        if self.content:
            return self.content[:200]
        if self.attachments.exists():
            return '📎 Attachment'
        return ''

class MessageAttachment(BaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='messages/%Y/%m/')
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self) -> str:
        return self.original_name

class MessageReceipt(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='receipts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_receipts')
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['message', 'user'], name='messagereceipt_unique')]
        indexes = [models.Index(fields=['user', '-read_at'])]
