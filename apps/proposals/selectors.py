from __future__ import annotations
from django.db.models import QuerySet
from apps.marketplace.models import Job
from apps.proposals.models import Proposal

def has_applied(job: Job, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Proposal.objects.filter(job=job, freelancer=user).exclude(status=Proposal.Status.WITHDRAWN).exists()

def proposals_for_job(job: Job) -> QuerySet[Proposal]:
    return Proposal.objects.filter(job=job).exclude(status=Proposal.Status.WITHDRAWN).select_related('freelancer', 'freelancer__freelancer_profile').order_by('-created_at')

def freelancer_proposals(user) -> QuerySet[Proposal]:
    return Proposal.objects.filter(freelancer=user).select_related('job', 'job__client', 'job__category').order_by('-created_at')

def get_proposal(public_id, user=None) -> Proposal:
    qs = Proposal.objects.select_related('job', 'job__client', 'job__category', 'freelancer', 'freelancer__freelancer_profile')
    proposal = qs.get(public_id=public_id)
    if user and user.is_authenticated:
        if not user.is_platform_admin and user.pk not in {proposal.freelancer_id, proposal.job.client_id}:
            raise Proposal.DoesNotExist
    return proposal
