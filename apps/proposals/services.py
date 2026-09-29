from __future__ import annotations
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.core.exceptions import DuplicateProposal, InvalidState, PermissionDenied, ValidationFailed
from apps.core.models import ActivityVerb
from apps.core.money import ZERO, positive_coin
from apps.core.permissions import require_verified_freelancer
from apps.core.services import record_activity
from apps.marketplace.models import Job
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
from apps.proposals.models import Proposal

@transaction.atomic()
def submit_proposal(*, job: Job, freelancer, cover_letter: str, proposed_amount, estimated_days: int, deliverables: str='', revision_limit: int=2, additional_message: str='') -> Proposal:
    require_verified_freelancer(freelancer)
    job = Job.objects.select_for_update().get(pk=job.pk)
    if not job.is_open:
        raise InvalidState('This job is no longer accepting proposals.')
    if job.client_id == freelancer.pk:
        raise PermissionDenied('You cannot propose against your own job.')
    if job.is_overdue:
        raise ValidationFailed('The deadline for this job has already passed.')
    existing = Proposal.objects.filter(job=job, freelancer=freelancer).exclude(status=Proposal.Status.WITHDRAWN).first()
    if existing:
        raise DuplicateProposal('You already have an active proposal submitted for this job.')
    proposed_amount = positive_coin(proposed_amount)
    if proposed_amount <= ZERO:
        raise ValidationFailed('Proposed amount must be greater than zero.')
    if estimated_days < 1:
        raise ValidationFailed('Estimated days must be at least 1.')
    cover_letter = (cover_letter or '').strip()
    if len(cover_letter) < 30:
        raise ValidationFailed('Cover letter must be at least 30 characters.')
    proposal = Proposal.objects.create(job=job, freelancer=freelancer, cover_letter=cover_letter, proposed_amount=proposed_amount, estimated_days=estimated_days, deliverables=deliverables.strip(), revision_limit=revision_limit, additional_message=additional_message.strip(), status=Proposal.Status.SUBMITTED)
    Job.objects.filter(pk=job.pk).update(proposal_count=F('proposal_count') + 1, status=Job.Status.PROPOSAL_RECEIVED if job.status == Job.Status.OPEN else job.status)
    notify(recipient=job.client, kind=NotificationType.NEW_PROPOSAL, title=f'New proposal for “{job.title}”', message=f'{freelancer.full_name} proposed {proposed_amount:,.2f} SkillCoin ({estimated_days} days).', actor=freelancer, target_url=proposal.get_absolute_url(), level='INFO', email=True)
    record_activity(ActivityVerb.PROPOSAL_SUBMITTED, f'Submitted proposal of {proposed_amount:,.2f} SKC for “{job.title}”', actor=freelancer, job=job, target=proposal, target_url=proposal.get_absolute_url(), amount=proposed_amount)
    from apps.profiles.models import FreelancerProfile
    FreelancerProfile.objects.filter(user=freelancer).update(proposals_submitted=F('proposals_submitted') + 1)
    return proposal

@transaction.atomic()
def withdraw_proposal(*, proposal: Proposal, actor) -> Proposal:
    proposal = Proposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.freelancer_id != actor.pk and (not actor.is_platform_admin):
        raise PermissionDenied('You can only withdraw your own proposals.')
    if not proposal.can_withdraw:
        raise InvalidState('This proposal cannot be withdrawn in its current state.')
    proposal.status = Proposal.Status.WITHDRAWN
    proposal.responded_at = timezone.now()
    proposal.save(update_fields=['status', 'responded_at', 'updated_at'])
    Job.objects.filter(pk=proposal.job_id, proposal_count__gt=0).update(proposal_count=F('proposal_count') - 1)
    record_activity(ActivityVerb.PROPOSAL_WITHDRAWN, f'Withdrew proposal for “{proposal.job.title}”', actor=actor, job=proposal.job, target=proposal)
    return proposal

@transaction.atomic()
def reject_proposal(*, proposal: Proposal, actor, reason: str='') -> Proposal:
    proposal = Proposal.objects.select_for_update().get(pk=proposal.pk)
    if proposal.job.client_id != actor.pk and (not actor.is_platform_admin):
        raise PermissionDenied('Only the job client can reject proposals.')
    if not proposal.is_open:
        raise InvalidState('This proposal is already closed.')
    proposal.status = Proposal.Status.REJECTED
    proposal.rejection_reason = reason.strip()
    proposal.responded_at = timezone.now()
    proposal.save(update_fields=['status', 'rejection_reason', 'responded_at', 'updated_at'])
    notify(recipient=proposal.freelancer, kind=NotificationType.PROPOSAL_REJECTED, title=f'Proposal update for “{proposal.job.title}”', message=reason.strip() or 'The client decided not to proceed with your proposal.', actor=actor, target_url=proposal.job.get_absolute_url(), level='WARNING')
    record_activity(ActivityVerb.PROPOSAL_REJECTED, f'Declined proposal from {proposal.freelancer.full_name}', actor=actor, job=proposal.job, target=proposal)
    return proposal
