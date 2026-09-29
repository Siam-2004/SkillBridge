from __future__ import annotations
from django.conf import settings
from django.db import models
from django.urls import reverse
from apps.core.models import BaseModel
from apps.core.money import ZERO, MoneyField

class Agreement(BaseModel):

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        IN_PROGRESS = ('IN_PROGRESS', 'In progress')
        COMPLETED = ('COMPLETED', 'Completed')
        CANCELLED = ('CANCELLED', 'Cancelled')
    job = models.ForeignKey('marketplace.Job', on_delete=models.PROTECT, related_name='agreements')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='client_agreements')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='freelancer_agreements')
    offer = models.ForeignKey('negotiations.Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='agreements')
    amount = MoneyField()
    deadline = models.DateTimeField()
    deliverables = models.TextField()
    revision_limit = models.PositiveSmallIntegerField(default=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    work_submission = models.TextField(blank=True)
    submission_link = models.URLField(max_length=500, blank=True, help_text='Google Drive, Dropbox, GitHub, Figma, or live demo link')
    submission_file = models.FileField(upload_to='agreements/submissions/%Y/%m/', null=True, blank=True, help_text='Proof of work, screenshot, deliverables archive or document')
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    client_feedback = models.TextField(blank=True)
    payment_transaction = models.ForeignKey('wallets.WalletTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='paid_agreements')

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f'Agreement<{self.public_id}> for {self.job.title}'

    @property
    def is_completed(self) -> bool:
        return self.status == self.Status.COMPLETED

    @property
    def has_submitted_work(self) -> bool:
        return bool(self.work_submission.strip() or self.submission_link or self.submission_file)

    @property
    def is_submission_image(self) -> bool:
        if not self.submission_file:
            return False
        name = self.submission_file.name.lower()
        return name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))

    def get_absolute_url(self) -> str:
        return reverse('agreements:detail', args=[self.public_id])

class AgreementAttachment(BaseModel):
    agreement = models.ForeignKey(Agreement, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='agreements/attachments/%Y/%m/')
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ('created_at',)

    @property
    def is_image(self) -> bool:
        name = self.original_name.lower()
        return name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))

    def __str__(self) -> str:
        return self.original_name
