from __future__ import annotations
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.core.exceptions import InvalidState, PermissionDenied, ValidationFailed
from apps.core.money import positive_coin
from apps.core.permissions import require_verified
from apps.marketplace.models import Job
from apps.negotiations.models import Negotiation, Offer
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
from apps.proposals.models import Proposal

def _expiry() -> timezone.datetime:
    return timezone.now() + timedelta(hours=settings.BUSINESS_RULES['OFFER_EXPIRY_HOURS'])

@transaction.atomic()
def open_negotiation(*, proposal: Proposal, actor) -> Negotiation:
    require_verified(actor)
    job = proposal.job
    if actor.pk not in {job.client_id, proposal.freelancer_id}:
        raise PermissionDenied('Only the client or the proposing freelancer can negotiate.')
    if not proposal.is_open:
        raise InvalidState('This proposal is closed.')
    existing = Negotiation.objects.filter(proposal=proposal).first()
    if existing:
        if not existing.is_active:
            raise InvalidState('This negotiation is already closed.')
        return existing
    negotiation = Negotiation.objects.create(job=job, proposal=proposal, client=job.client, freelancer=proposal.freelancer)
    first_offer = Offer.objects.create(negotiation=negotiation, sender=proposal.freelancer, receiver=job.client, round_number=1, amount=proposal.proposed_amount, deadline=job.deadline, deliverables=proposal.deliverables, revision_limit=proposal.revision_limit, requirements=job.requirements, message=proposal.additional_message or 'Terms as proposed.', expires_at=_expiry())
    negotiation.current_offer = first_offer
    negotiation.round_count = 1
    negotiation.save(update_fields=['current_offer', 'round_count', 'updated_at'])
    Proposal.objects.filter(pk=proposal.pk).update(status=Proposal.Status.NEGOTIATING)
    Job.objects.filter(pk=job.pk).exclude(status__in=[Job.Status.HIRED, Job.Status.IN_PROGRESS, Job.Status.COMPLETED]).update(status=Job.Status.NEGOTIATING)
    record_activity(ActivityVerb.NEGOTIATION_OPENED, f'Opened negotiation for “{job.title}”', actor=actor, job=job, target=negotiation, target_url=negotiation.get_absolute_url())
    notify(negotiation.other_party(actor), NotificationType.NEW_OFFER, f'Negotiation opened for “{job.title}”', message=f'Opening terms: {first_offer.amount:,.2f} SKC.', actor=actor, target_url=_room_url(negotiation, negotiation.other_party(actor)), email=True)
    return negotiation

@transaction.atomic()
def send_offer(*, negotiation: Negotiation, sender, amount, deadline, deliverables: str, revision_limit: int=2, requirements: str='', message: str='', is_final: bool=False) -> Offer:
    require_verified(sender)
    negotiation = Negotiation.objects.select_for_update().get(pk=negotiation.pk)
    if not negotiation.is_active:
        raise InvalidState('This negotiation is closed.')
    if sender.pk not in {negotiation.client_id, negotiation.freelancer_id}:
        raise PermissionDenied('You are not part of this negotiation.')
    current = negotiation.current_offer
    if current and current.is_actionable and (current.sender_id == sender.pk):
        raise InvalidState('Your offer is still awaiting a response.')
    if current and current.is_actionable and current.is_final:
        raise InvalidState('The other party marked their offer as final — accept or decline it.')
    amount = positive_coin(amount)
    if deadline <= timezone.now():
        raise ValidationFailed('The proposed deadline must be in the future.')
    if not deliverables.strip():
        raise ValidationFailed('List the deliverables this offer covers.')
    receiver = negotiation.other_party(sender)
    if current and current.status == Offer.Status.ACTIVE:
        _supersede(current, Offer.Status.COUNTERED)
    offer = Offer.objects.create(negotiation=negotiation, sender=sender, receiver=receiver, round_number=negotiation.round_count + 1, amount=amount, deadline=deadline, deliverables=deliverables.strip(), revision_limit=revision_limit, requirements=requirements.strip(), message=message.strip(), is_final=is_final, expires_at=_expiry(), replies_to=current)
    negotiation.current_offer = offer
    negotiation.round_count = offer.round_number
    negotiation.save(update_fields=['current_offer', 'round_count', 'updated_at'])
    verb = ActivityVerb.COUNTER_OFFER if current else ActivityVerb.OFFER_CREATED
    record_activity(verb, f"{('Final offer' if is_final else 'Offer')} of {amount:,.2f} SKC (round {offer.round_number})", actor=sender, job=negotiation.job, target=offer, target_url=negotiation.get_absolute_url(), amount=amount)
    notify(receiver, NotificationType.COUNTER_OFFER if current else NotificationType.NEW_OFFER, f"{('Final offer' if is_final else 'New offer')}: {amount:,.2f} SKC", message=f'For “{negotiation.job.title}”. ' + (message[:200] if message else 'Review the terms and respond.'), actor=sender, target_url=_room_url(negotiation, receiver), email=True)
    return offer

@transaction.atomic()
def reject_offer(*, offer: Offer, actor, note: str='') -> Offer:
    require_verified(actor)
    offer = Offer.objects.select_for_update().get(pk=offer.pk)
    if not offer.can_be_actioned_by(actor):
        raise PermissionDenied('This offer is not awaiting your response.')
    _supersede(offer, Offer.Status.REJECTED, note=note)
    negotiation = offer.negotiation
    negotiation.current_offer = None
    negotiation.save(update_fields=['current_offer', 'updated_at'])
    record_activity(ActivityVerb.OFFER_REJECTED, f'Declined the {offer.amount:,.2f} SKC offer', actor=actor, job=negotiation.job, target=offer)
    notify(offer.sender, NotificationType.COUNTER_OFFER, 'Your offer was declined', message=note[:400] or 'You can send revised terms.', actor=actor, target_url=_room_url(negotiation, offer.sender))
    return offer

@transaction.atomic()
def cancel_negotiation(*, negotiation: Negotiation, actor, reason: str='') -> Negotiation:
    negotiation = Negotiation.objects.select_for_update().get(pk=negotiation.pk)
    if not negotiation.is_active:
        return negotiation
    if negotiation.current_offer_id:
        _supersede(negotiation.current_offer, Offer.Status.WITHDRAWN, note=reason)
    negotiation.status = Negotiation.Status.CANCELLED
    negotiation.current_offer = None
    negotiation.closed_at = timezone.now()
    negotiation.save(update_fields=['status', 'current_offer', 'closed_at', 'updated_at'])
    return negotiation

@transaction.atomic()
def accept_offer(*, offer: Offer, actor):
    require_verified(actor)
    offer = Offer.objects.select_for_update().get(pk=offer.pk)
    if not offer.can_be_actioned_by(actor):
        raise PermissionDenied('This offer is not awaiting your response.')
    if offer.deadline <= timezone.now():
        raise InvalidState('The deadline in this offer has passed. Ask for revised terms.')
    negotiation = Negotiation.objects.select_for_update().get(pk=offer.negotiation_id)
    job = Job.objects.select_for_update().get(pk=negotiation.job_id)
    if offer.amount > job.reserved_amount:
        from apps.core.exceptions import InsufficientFunds
        from apps.wallets.selectors import get_wallet
        shortfall = offer.amount - job.reserved_amount
        wallet = get_wallet(job.client)
        if wallet.available_balance < shortfall:
            raise InsufficientFunds(f'These terms ({offer.amount:,.2f} SKC) exceed the reserved job budget ({job.reserved_amount:,.2f} SKC). The client must deposit {shortfall - wallet.available_balance:,.2f} SKC more before accepting.', required=shortfall, available=wallet.available_balance)
        from apps.wallets import ledger
        ledger.reserve_job_budget(user=job.client, amount=shortfall, job=job, actor=actor)
        job.reserved_amount = job.reserved_amount + shortfall
        job.budget = max(job.budget, offer.amount)
        job.save(update_fields=['reserved_amount', 'budget', 'updated_at'])
    _supersede(offer, Offer.Status.ACCEPTED)
    negotiation.status = Negotiation.Status.ACCEPTED
    negotiation.closed_at = timezone.now()
    negotiation.save(update_fields=['status', 'closed_at', 'updated_at'])
    from apps.agreements.services import create_agreement_from_offer
    agreement = create_agreement_from_offer(offer=offer, actor=actor)
    record_activity(ActivityVerb.OFFER_ACCEPTED, f'Accepted terms at {offer.amount:,.2f} SKC', actor=actor, job=job, target=offer, amount=offer.amount)
    notify(offer.sender, NotificationType.AGREEMENT_ACCEPTED, f'Terms accepted for “{job.title}”', message=f'Final amount {offer.amount:,.2f} SKC. The agreement is ready.', actor=actor, target_url=_agreement_url(agreement, offer.sender), level='SUCCESS', email=True)
    return agreement

def _supersede(offer: Offer, status: str, *, note: str='') -> None:
    offer.status = status
    offer.responded_at = timezone.now()
    if note:
        offer.response_note = note[:1000]
    offer.save(update_fields=['status', 'responded_at', 'response_note', 'updated_at'])

def expire_stale_offers() -> int:
    now = timezone.now()
    stale = list(Offer.objects.filter(status=Offer.Status.ACTIVE, expires_at__isnull=False, expires_at__lte=now).select_related('negotiation', 'sender', 'receiver', 'negotiation__job'))
    for offer in stale:
        with transaction.atomic():
            _supersede(offer, Offer.Status.EXPIRED)
            Negotiation.objects.filter(pk=offer.negotiation_id, current_offer=offer).update(current_offer=None)
            notify(offer.receiver, NotificationType.OFFER_EXPIRED, 'An offer expired', message=f'The {offer.amount:,.2f} SKC offer for “{offer.negotiation.job.title}” expired without a response.', target_url=_room_url(offer.negotiation, offer.receiver))
    return len(stale)

def _room_url(negotiation: Negotiation, user=None) -> str:
    return f'/negotiations/{negotiation.public_id}/'

def _agreement_url(agreement, user=None) -> str:
    return f'/agreements/{agreement.public_id}/'
