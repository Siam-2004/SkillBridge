from __future__ import annotations
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.core.exceptions import InsufficientFunds, InvalidState, PermissionDenied, ValidationFailed
from apps.core.money import ZERO, positive_coin
from apps.core.permissions import require_verified_client
from apps.core.selectors import invalidate_platform_stats
from apps.marketplace.models import Job
from apps.profiles.models import Category, Skill
from apps.notifications.models import NotificationType
from apps.notifications.services import notify, notify_many
from apps.wallets import ledger
from apps.wallets.selectors import get_wallet

@transaction.atomic()
def create_job(*, client, title: str, category: Category, description: str, budget, deadline, skills=None, requirements: str='', job_type: str=Job.JobType.FIXED, complexity: str=Job.Complexity.INTERMEDIATE, experience_level: str=Job.Experience.INTERMEDIATE, estimated_days: int | None=None, people_required: int=1, team_required: bool=False, publish: bool=False) -> Job:
    require_verified_client(client)
    budget = positive_coin(budget)
    if deadline and deadline <= timezone.now():
        raise ValidationFailed('The deadline must be in the future.')
    if people_required < 1:
        raise ValidationFailed('At least one freelancer is required.')
    job = Job.objects.create(client=client, title=title.strip()[:200], category=category, description=description.strip(), requirements=requirements.strip(), budget=budget, deadline=deadline, job_type=job_type, complexity=complexity, experience_level=experience_level, estimated_days=estimated_days, people_required=people_required, team_required=team_required, status=Job.Status.DRAFT)
    if skills:
        job.skills.set(skills)
        Skill.objects.filter(pk__in=[s.pk for s in skills]).update(usage_count=F('usage_count') + 1)
    record_activity(ActivityVerb.JOB_CREATED, f'Created job “{job.title}”', actor=client, job=job, target=job, visibility='ACTOR_ONLY', budget=budget)
    if publish:
        job = publish_job(job=job, client=client)
    return job

@transaction.atomic()
def publish_job(*, job: Job, client) -> Job:
    require_verified_client(client)
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.client_id != client.pk:
        raise PermissionDenied('You can only publish your own jobs.')
    if job.status != Job.Status.DRAFT:
        raise InvalidState('Only a draft job can be published.')
    if job.deadline <= timezone.now():
        raise ValidationFailed('Update the deadline before publishing — it has passed.')
    wallet = ledger.lock_wallet(client)
    if wallet.available_balance < job.budget:
        raise InsufficientFunds(f'Publishing this job needs {job.budget:,.2f} SKC in your available balance; you have {wallet.available_balance:,.2f} SKC. Deposit {job.budget - wallet.available_balance:,.2f} SKC to continue.', required=job.budget, available=wallet.available_balance)
    txn = ledger.reserve_job_budget(user=client, amount=job.budget, job=job, actor=client, wallet=wallet)
    job.status = Job.Status.OPEN
    job.published_at = timezone.now()
    job.budget_reserved_at = timezone.now()
    job.reserve_transaction = txn
    job.reserved_amount = job.budget
    job.save(update_fields=['status', 'published_at', 'budget_reserved_at', 'reserve_transaction', 'reserved_amount', 'updated_at'])
    reindex_job(job)
    from apps.profiles.models import ClientProfile
    ClientProfile.objects.filter(user=client).update(jobs_posted=Job.objects.alive().filter(client=client).exclude(status=Job.Status.DRAFT).count())
    record_activity(ActivityVerb.JOB_PUBLISHED, f'Published job “{job.title}” and reserved {job.budget:,.2f} SKC', actor=client, job=job, target=job, target_url=job.get_absolute_url(), visibility='PUBLIC', budget=job.budget)
    record_activity(ActivityVerb.BUDGET_RESERVED, f'{job.budget:,.2f} SKC reserved for “{job.title}”', actor=client, job=job, target=txn, visibility='ACTOR_ONLY')
    transaction.on_commit(invalidate_platform_stats)
    return job

@transaction.atomic()
def update_job(*, job: Job, client, **fields) -> Job:
    require_verified_client(client)
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.client_id != client.pk:
        raise PermissionDenied('You can only edit your own jobs.')
    if job.status not in Job.CANCELLABLE_STATUSES:
        raise InvalidState('This job can no longer be edited — work has started.')
    if 'budget' in fields:
        new_budget = positive_coin(fields.pop('budget'))
        if new_budget != job.budget:
            if job.status != Job.Status.DRAFT:
                raise InvalidState('The budget of a published job is reserved and cannot be changed. Cancel the job to release the reservation, then repost it.')
            job.budget = new_budget
    skills = fields.pop('skills', None)
    editable = {'title', 'description', 'requirements', 'category', 'deadline', 'job_type', 'complexity', 'experience_level', 'estimated_days', 'people_required', 'team_required'}
    changed = []
    for key, value in fields.items():
        if key in editable:
            setattr(job, key, value)
            changed.append(key)
    if job.deadline <= timezone.now() and job.status != Job.Status.DRAFT:
        raise ValidationFailed('The deadline must stay in the future.')
    job.save()
    if skills is not None:
        job.skills.set(skills)
    reindex_job(job)
    return job

@transaction.atomic()
def cancel_job(*, job: Job, client, reason: str='') -> Job:
    require_verified_client(client)
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.client_id != client.pk:
        raise PermissionDenied('You can only cancel your own jobs.')
    if not job.can_cancel:
        raise InvalidState('A freelancer has already been hired for this job. Open a cancellation request or a dispute on the project instead.')
    released = job.reserved_amount
    if released > ZERO:
        ledger.release_job_budget(user=client, amount=released, job=job, actor=client, reason=reason)
        job.reserved_amount = ZERO
    job.status = Job.Status.CANCELLED
    job.cancelled_at = timezone.now()
    job.cancellation_reason = reason
    job.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'reserved_amount', 'updated_at'])
    from apps.proposals.models import Proposal
    open_proposals = list(Proposal.objects.filter(job=job, status__in=Proposal.OPEN_STATUSES).select_related('freelancer'))
    Proposal.objects.filter(pk__in=[p.pk for p in open_proposals]).update(status=Proposal.Status.REJECTED, rejection_reason='The client cancelled this job.', responded_at=timezone.now())
    notify_many([p.freelancer for p in open_proposals], NotificationType.JOB_CANCELLED, f'Job cancelled: {job.title}', message='The client withdrew this job, so your proposal has been closed.', actor=client, target_url='/proposals/', level='WARNING')
    record_activity(ActivityVerb.JOB_CANCELLED, f'Cancelled job “{job.title}”' + (f' — {reason}' if reason else ''), actor=client, job=job, target=job, visibility='PARTICIPANTS')
    if released > ZERO:
        record_activity(ActivityVerb.BUDGET_RELEASED, f'{released:,.2f} SKC returned to your available balance', actor=client, job=job, visibility='ACTOR_ONLY')
    transaction.on_commit(invalidate_platform_stats)
    return job

def reindex_job(job: Job) -> None:
    from apps.core.search import build_search_text
    skills = ' '.join(job.skills.values_list('name', flat=True))
    category = job.category.name if job.category_id else ''
    Job.objects.filter(pk=job.pk).update(search_text=build_search_text(job.title, job.title, skills, skills, category, job.description, job.requirements))

@transaction.atomic()
def record_job_view(*, job: Job, user=None, session_key: str='') -> None:
    from apps.marketplace.models import JobView
    if not user and (not session_key):
        return
    _, created = JobView.objects.get_or_create(job=job, user=user if user and user.is_authenticated else None, session_key='' if user and user.is_authenticated else session_key[:60], day=timezone.localdate())
    if created:
        Job.objects.filter(pk=job.pk).update(view_count=F('view_count') + 1)

@transaction.atomic()
def toggle_saved_job(*, job: Job, user) -> bool:
    from apps.marketplace.models import SavedJob
    existing = SavedJob.objects.filter(job=job, user=user).first()
    if existing:
        existing.delete()
        return False
    SavedJob.objects.create(job=job, user=user)
    return True

@transaction.atomic()
def moderate_job(*, job: Job, admin, flagged: bool, note: str='') -> Job:
    from apps.audit.models import AuditLog
    from apps.audit.services import record_audit
    from apps.core.permissions import require_admin
    require_admin(admin)
    previous = {'is_flagged': job.is_flagged, 'moderation_note': job.moderation_note}
    job.is_flagged = flagged
    job.moderation_note = note[:300]
    job.save(update_fields=['is_flagged', 'moderation_note', 'updated_at'])
    record_audit(AuditLog.Action.JOB_MODERATE, job, actor=admin, previous=previous, new={'is_flagged': flagged, 'moderation_note': job.moderation_note}, reason=note)
    if flagged:
        notify(job.client, NotificationType.ACCOUNT_NOTICE, f'Your job “{job.title}” needs attention', message=note[:500], actor=admin, level='WARNING', email=True)
    return job
