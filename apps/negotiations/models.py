from __future__ import annotations
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.models import BaseModel
from apps.core.money import ZERO, MoneyField

class Negotiation(BaseModel):

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        ACCEPTED = ('ACCEPTED', 'Accepted')
        REJECTED = ('REJECTED', 'Rejected')
        EXPIRED = ('EXPIRED', 'Expired')
        CANCELLED = ('CANCELLED', 'Cancelled')
    job = models.ForeignKey('marketplace.Job', on_delete=models.CASCADE, related_name='negotiations')
    proposal = models.OneToOneField('proposals.Proposal', on_delete=models.CASCADE, related_name='negotiation')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_negotiations')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='freelancer_negotiations')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    current_offer = models.OneToOneField('Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='is_current_for')
    round_count = models.PositiveSmallIntegerField(default=0)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['client', 'status']), models.Index(fields=['freelancer', 'status'])]

    def __str__(self) -> str:
        return f'negotiation<{self.public_id}>'

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    def participants(self):
        return [self.client, self.freelancer]

    def other_party(self, user):
        return self.freelancer if user.pk == self.client_id else self.client

    def get_absolute_url(self) -> str:
        return reverse('negotiations:room', args=[self.public_id])

class Offer(BaseModel):

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Awaiting response')
        ACCEPTED = ('ACCEPTED', 'Accepted')
        REJECTED = ('REJECTED', 'Rejected')
        COUNTERED = ('COUNTERED', 'Countered')
        EXPIRED = ('EXPIRED', 'Expired')
        WITHDRAWN = ('WITHDRAWN', 'Withdrawn')
    negotiation = models.ForeignKey(Negotiation, on_delete=models.CASCADE, related_name='offers')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offers_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offers_received')
    round_number = models.PositiveSmallIntegerField(default=1)
    amount = MoneyField()
    deadline = models.DateTimeField()
    deliverables = models.TextField(max_length=3000)
    revision_limit = models.PositiveSmallIntegerField(default=2)
    requirements = models.TextField(blank=True, max_length=3000)
    message = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_final = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    response_note = models.TextField(blank=True, max_length=1000)
    replies_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='counters')

    class Meta:
        ordering = ('round_number', 'created_at')
        constraints = [models.CheckConstraint(check=models.Q(amount__gt=ZERO), name='offer_amount_positive')]
        indexes = [models.Index(fields=['negotiation', 'round_number']), models.Index(fields=['receiver', 'status']), models.Index(fields=['status', 'expires_at'])]

    def __str__(self) -> str:
        return f'offer<{self.public_id}> {self.amount}'

    @property
    def is_actionable(self) -> bool:
        return self.status == self.Status.ACTIVE and (not self.is_expired)

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def deliverable_list(self) -> list[str]:
        return [d.strip(' -•') for d in self.deliverables.splitlines() if d.strip()]

    def can_be_actioned_by(self, user) -> bool:
        return self.is_actionable and user.pk == self.receiver_id and (self.negotiation.current_offer_id == self.pk)
