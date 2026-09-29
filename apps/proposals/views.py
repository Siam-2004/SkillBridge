"""Proposal views: submitting, viewing, and managing bids."""
from __future__ import annotations
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from apps.core.permissions import freelancer_required, verified_required
from apps.core.views import handle_domain_errors, paginate
from apps.marketplace.models import Job
from apps.proposals import selectors, services
from apps.proposals.forms import ProposalForm
from apps.proposals.models import Proposal

@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def create_proposal(request, job_id):
    job = get_object_or_404(Job.objects.alive(), public_id=job_id)
    if not job.is_open:
        messages.error(request, "This job is no longer accepting new proposals.")
        return redirect(job.get_absolute_url())
    if job.client_id == request.user.pk:
        messages.error(request, "You cannot submit a proposal to your own job posting.")
        return redirect(job.get_absolute_url())
    if selectors.has_applied(job, request.user):
        messages.info(request, "You have already submitted a proposal for this job.")
        return redirect(job.get_absolute_url())
    form = ProposalForm(request.POST or None, initial={"proposed_amount": job.budget, "estimated_days": job.estimated_days or 7, "deliverables": job.requirements, "revision_limit": 2})
    if request.method == "POST" and form.is_valid():
        proposal = services.submit_proposal(job=job, freelancer=request.user, **form.cleaned_data)
        messages.success(request, f"Your proposal of {proposal.proposed_amount:,.2f} SkillCoin for “{job.title}” " "has been submitted! The client has been notified.")
        return redirect(proposal.get_absolute_url())
    return render(request, "proposals/form.html", {"form": form, "job": job, "nav_section": "jobs", "page_title": f"Submit Proposal — {job.title}"})

@verified_required
@handle_domain_errors
def proposal_detail(request, public_id):
    try:
        proposal = selectors.get_proposal(public_id, request.user)
    except Proposal.DoesNotExist as exc:
        raise Http404("Proposal not found.") from exc
    is_client = request.user.pk == proposal.job.client_id
    is_freelancer = request.user.pk == proposal.freelancer_id
    # Check if a negotiation room already exists
    negotiation = getattr(proposal, "negotiation", None)
    from apps.messaging.models import Conversation
    conversation = Conversation.objects.filter(job=proposal.job, participants__user=proposal.freelancer).first()
    return render(request, "proposals/detail.html", {"proposal": proposal, "job": proposal.job, "is_client": is_client, "is_freelancer": is_freelancer, "negotiation": negotiation, "conversation": conversation, "nav_section": "jobs", "page_title": f"Proposal: {proposal.freelancer.full_name} for {proposal.job.title}"})

@verified_required
def proposals_for_job_view(request, job_id):
    job = get_object_or_404(Job.objects.alive(), public_id=job_id)
    if job.client_id != request.user.pk and not request.user.is_platform_admin:
        messages.error(request, "Only the client who posted the job can view all proposals.")
        return redirect(job.get_absolute_url())
    proposals_qs = selectors.proposals_for_job(job)
    page, querystring = paginate(request, proposals_qs, 12)
    return render(request, "proposals/job_proposals.html", {"job": job, "page": page, "querystring": querystring, "total": page.paginator.count, "nav_section": "jobs", "page_title": f"Proposals for “{job.title}”"})

@freelancer_required
def my_proposals_view(request):
    proposals_qs = selectors.freelancer_proposals(request.user)
    status_filter = request.GET.get("status", "")
    if status_filter:
        proposals_qs = proposals_qs.filter(status=status_filter)
    page, querystring = paginate(request, proposals_qs, 15)
    return render(request, "proposals/my_proposals.html", {"page": page, "querystring": querystring, "statuses": Proposal.Status.choices, "current_status": status_filter, "nav_section": "jobs", "nav": "proposals", "page_title": "My Proposals"})

@freelancer_required
@handle_domain_errors
@require_http_methods(["POST"])
def withdraw_proposal_view(request, public_id):
    proposal = get_object_or_404(Proposal, public_id=public_id, freelancer=request.user)
    services.withdraw_proposal(proposal=proposal, actor=request.user)
    messages.info(request, "Your proposal has been withdrawn.")
    return redirect("proposals:my_proposals")

@verified_required
@handle_domain_errors
@require_http_methods(["POST"])
def reject_proposal_view(request, public_id):
    proposal = get_object_or_404(Proposal, public_id=public_id, job__client=request.user)
    reason = request.POST.get("reason", "").strip()
    services.reject_proposal(proposal=proposal, actor=request.user, reason=reason)
    messages.info(request, "Proposal declined.")
    return redirect("proposals:for_job", job_id=proposal.job.public_id)