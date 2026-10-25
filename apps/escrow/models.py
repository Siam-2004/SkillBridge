from __future__ import annotations
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField

class Escrow(BaseModel):

    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active')
        PARTIALLY_RELEASED = ('PARTIALLY_RELEASED', 'Partially released')
        RELEASED = ('RELEASED', 'Released')
        DISPUTED = ('DISPUTED', 'Disputed')
        REFUNDED = ('REFUNDED', 'Refunded')
    project = models.OneToOneField('projects.Project', on_delete=models.PROTECT, related_name='escrow')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='escrows')
    agreement = models.ForeignKey('agreements.Agreement', on_delete=models.PROTECT, related_name='escrows')
    funded_amount = MoneyField(help_text='Total ever placed in escrow for this project.')
    held_amount = MoneyField(help_text='Still locked.')
    released_amount = MoneyField(help_text='Paid out to freelancers.')
    refunded_amount = MoneyField(help_text='Returned to the client.')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    funded_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)
    hold_transaction = models.ForeignKey('wallets.WalletTransaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='escrow_holds')
    is_locked = models.BooleanField(default=False, help_text='An open dispute freezes every movement.')
    lock_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(held_amount__gte=ZERO), name='escrow_held_non_negative'), models.CheckConstraint(check=models.Q(funded_amount=models.F('held_amount') + models.F('released_amount') + models.F('refunded_amount')), name='escrow_balances_reconcile')]

    def __str__(self) -> str:
        return f'escrow<{self.public_id}> {self.held_amount}/{self.funded_amount}'

    @property
    def amount(self):
        return self.funded_amount

    @property
    def is_exhausted(self) -> bool:
        return self.held_amount <= ZERO

    @property
    def release_percent(self) -> int:
        if self.funded_amount <= ZERO:
            return 0
        return int(self.released_amount / self.funded_amount * 100)

    @property
    def allocated_total(self):
        from django.db.models import Sum
        from apps.tasks.models import Task
        return Task.objects.filter(project_id=self.project_id).exclude(status=Task.Status.CANCELLED).aggregate(total=Sum('skillcoin_allocation'))['total'] or ZERO

    @property
    def unallocated_amount(self):
        return self.funded_amount - self.allocated_total

    @property
    def allocations_balanced(self) -> bool:
        return self.allocated_total == self.funded_amount

