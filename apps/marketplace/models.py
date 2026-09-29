from __future__ import annotations
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from apps.core.models import BaseModel, SoftDeleteModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField

class JobQuerySet(models.QuerySet):

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def public(self):
        return self.alive().filter(status__in=Job.PUBLIC_STATUSES)

    def open_to_proposals(self):
        return self.alive().filter(status__in=Job.OPEN_STATUSES)

    def for_client(self, client):
        return self.alive().filter(client=client)

class Job(SoftDeleteModel, BaseModel):

    class Status(models.TextChoices):
        DRAFT = ('DRAFT', 'Draft')
        OPEN = ('OPEN', 'Open')
        PROPOSAL_RECEIVED = ('PROPOSAL_RECEIVED', 'Proposals received')
        NEGOTIATING = ('NEGOTIATING', 'Negotiating')
        HIRED = ('HIRED', 'Freelancer hired')
        IN_PROGRESS = ('IN_PROGRESS', 'In progress')
        COMPLETED = ('COMPLETED', 'Completed')
        CANCELLED = ('CANCELLED', 'Cancelled')

    class JobType(models.TextChoices):
        FIXED = ('FIXED', 'Fixed price')
        HOURLY = ('HOURLY', 'Hourly')
        MILESTONE = ('MILESTONE', 'Milestone based')

    class Complexity(models.TextChoices):
        SIMPLE = ('SIMPLE', 'Simple')
        INTERMEDIATE = ('INTERMEDIATE', 'Intermediate')
        COMPLEX = ('COMPLEX', 'Complex')
        EXPERT = ('EXPERT', 'Expert')

    class Experience(models.TextChoices):
        ENTRY = ('ENTRY', 'Entry level')
        INTERMEDIATE = ('INTERMEDIATE', 'Intermediate')
        EXPERT = ('EXPERT', 'Expert')
    PUBLIC_STATUSES = [Status.OPEN, Status.PROPOSAL_RECEIVED, Status.NEGOTIATING, Status.HIRED, Status.IN_PROGRESS, Status.COMPLETED]
    OPEN_STATUSES = [Status.OPEN, Status.PROPOSAL_RECEIVED, Status.NEGOTIATING]
    CANCELLABLE_STATUSES = [Status.DRAFT, Status.OPEN, Status.PROPOSAL_RECEIVED, Status.NEGOTIATING]
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='jobs')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, db_index=True)
    category = models.ForeignKey('profiles.Category', on_delete=models.PROTECT, related_name='jobs')
    description = models.TextField()
    requirements = models.TextField(blank=True)
    skills = models.ManyToManyField('profiles.Skill', related_name='jobs', blank=True)
    budget = MoneyField(help_text='Committed budget; reserved on publish.')
    job_type = models.CharField(max_length=10, choices=JobType.choices, default=JobType.FIXED)
    complexity = models.CharField(max_length=12, choices=Complexity.choices, default=Complexity.INTERMEDIATE)
    experience_level = models.CharField(max_length=12, choices=Experience.choices, default=Experience.INTERMEDIATE)
    deadline = models.DateTimeField()
    estimated_days = models.PositiveSmallIntegerField(null=True, blank=True)
    people_required = models.PositiveSmallIntegerField(default=1, help_text='How many freelancers the work needs.')
    team_required = models.BooleanField(default=False, help_text='The hired freelancer is expected to build a team.')
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.DRAFT, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    visibility_note = models.CharField(max_length=200, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    budget_reserved_at = models.DateTimeField(null=True, blank=True)
    reserve_transaction = models.ForeignKey('wallets.WalletTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='reserved_jobs')
    reserved_amount = MoneyField(help_text='Currently held in reserve for this job.')
    hired_freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hired_jobs')
    hired_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    proposal_count = models.PositiveIntegerField(default=0, db_index=True)
    view_count = models.PositiveIntegerField(default=0)
    message_count = models.PositiveIntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
    moderation_note = models.CharField(max_length=300, blank=True)
    search_text = models.TextField(blank=True, editable=False, db_index=True)
    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ('-published_at', '-created_at')
        indexes = [models.Index(fields=['status', '-published_at']), models.Index(fields=['client', '-created_at']), models.Index(fields=['category', 'status']), models.Index(fields=['-budget']), models.Index(fields=['deadline']), models.Index(fields=['search_text'], name='job_search_text')]
        constraints = [models.CheckConstraint(check=models.Q(budget__gt=ZERO), name='job_budget_positive'), models.CheckConstraint(check=models.Q(people_required__gte=1), name='job_people_required_min'), models.CheckConstraint(check=~models.Q(status__in=['OPEN', 'PROPOSAL_RECEIVED', 'NEGOTIATING']) | models.Q(budget_reserved_at__isnull=False), name='job_open_requires_reservation')]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:240] or 'job'
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES and (not self.is_deleted)

    @property
    def is_public(self) -> bool:
        return self.status in self.PUBLIC_STATUSES and (not self.is_deleted)

    @property
    def can_cancel(self) -> bool:
        return self.status in self.CANCELLABLE_STATUSES and self.hired_freelancer_id is None

    @property
    def is_overdue(self) -> bool:
        return bool(self.deadline and self.deadline < timezone.now())

    @property
    def days_left(self) -> int | None:
        if not self.deadline:
            return None
        return max((self.deadline - timezone.now()).days, 0)

    def get_absolute_url(self) -> str:
        return reverse('marketplace:job_detail', args=[self.public_id])

class JobAttachment(TimeStampedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='jobs/%Y/%m/')
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='job_uploads')
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self) -> str:
        return self.original_name

class JobView(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=60, blank=True)
    day = models.DateField(default=timezone.localdate)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'user', 'day'], condition=models.Q(user__isnull=False), name='jobview_unique_user_day'), models.UniqueConstraint(fields=['job', 'session_key', 'day'], condition=models.Q(user__isnull=True), name='jobview_unique_session_day')]

class SavedJob(TimeStampedModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saves')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_jobs')

    class Meta:
        ordering = ('-created_at',)
        constraints = [models.UniqueConstraint(fields=['job', 'user'], name='savedjob_unique')]
