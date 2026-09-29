"""Jobs: browsing, posting, editing and cancelling."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.permissions import client_required
from apps.core.views import handle_domain_errors, paginate
from apps.marketplace import services
from apps.marketplace.forms import CancelJobForm, JobFilterForm, JobForm
from apps.marketplace.models import Job, SavedJob
from apps.marketplace.selectors import (
    client_jobs,
    job_detail,
    search_jobs,
    similar_jobs,
)


# --------------------------------------------------------------------------- #
# Public browsing
# --------------------------------------------------------------------------- #
def job_list(request):
    form = JobFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}

    results = search_jobs(
        keyword=data.get("q") or "",
        category=data.get("category"),
        skills=data.get("skills") or None,
        min_budget=data.get("min_budget"),
        max_budget=data.get("max_budget"),
        deadline_before=data.get("deadline_before"),
        experience_level=data.get("experience_level") or "",
        job_type=data.get("job_type") or "",
        complexity=data.get("complexity") or "",
        people=data.get("people") or "",
        team_required=data.get("team_required") or "",
        status=data.get("status") or "",
        sort=data.get("sort") or "newest",
        viewer=request.user,
    )
    page, querystring = paginate(request, results, 12)

    saved_ids = set()
    if request.user.is_authenticated:
        saved_ids = set(
            SavedJob.objects.filter(user=request.user).values_list("job_id", flat=True)
        )

    return render(
        request,
        "marketplace/job_list.html",
        {
            "form": form,
            "page": page,
            "querystring": querystring,
            "total": page.paginator.count,
            "saved_ids": saved_ids,
            "nav_section": "jobs",
            "nav": "jobs",
            "page_title": "Jobs",
        },
    )


def job_detail_view(request, public_id):
    try:
        job = job_detail(public_id, viewer=request.user)
    except Job.DoesNotExist as exc:
        raise Http404("No such job.") from exc

    services.record_job_view(
        job=job,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
    )

    context = {
        "job": job,
        "similar": similar_jobs(job),
        "is_owner": request.user.is_authenticated and request.user.pk == job.client_id,
        "nav_section": "jobs",
        "nav": "jobs",
        "page_title": job.title,
    }

    from apps.agreements.models import Agreement
    from apps.messaging.models import Conversation

    agreement = (
        Agreement.objects.filter(job=job)
        .select_related("freelancer", "client", "offer")
        .first()
    )
    context["agreement"] = agreement

    if request.user.is_authenticated and request.user.is_freelancer:
        from apps.proposals.selectors import has_applied
        from apps.proposals.models import Proposal

        context["has_applied"] = has_applied(job, request.user)
        context["my_proposal"] = (
            Proposal.objects.filter(job=job, freelancer=request.user)
            .select_related("negotiation")
            .first()
        )
        context["is_saved"] = SavedJob.objects.filter(
            user=request.user, job=job
        ).exists()
        context["my_conversation"] = (
            Conversation.objects.filter(job=job, participants__user=request.user).first()
        )

    if context["is_owner"]:
        from apps.proposals.selectors import proposals_for_job

        context["proposals"] = proposals_for_job(job)[:10]

        job_conversations = list(
            Conversation.objects.filter(job=job)
            .select_related("initiator")
            .prefetch_related("participants__user")
            .order_by("-last_message_at", "-created_at")
        )
        for c in job_conversations:
            c.freelancer_participant = next(
                (p.user for p in c.participants.all() if p.user_id != request.user.pk),
                c.initiator,
            )
        context["job_conversations"] = job_conversations

    return render(request, "marketplace/job_detail.html", context)


# --------------------------------------------------------------------------- #
# Client job management
# --------------------------------------------------------------------------- #
@client_required
def my_jobs(request):
    jobs = client_jobs(
        request.user,
        status=request.GET.get("status", ""),
        search=request.GET.get("q", ""),
    )
    page, querystring = paginate(request, jobs, 15)
    return render(
        request,
        "marketplace/my_jobs.html",
        {
            "page": page,
            "querystring": querystring,
            "statuses": Job.Status.choices,
            "current_status": request.GET.get("status", ""),
            "query": request.GET.get("q", ""),
            "nav": "my_jobs",
            "page_title": "My jobs",
        },
    )


@client_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def job_create(request):
    from apps.wallets.selectors import wallet_summary

    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        skills = data.pop("skills", None)
        publish = request.POST.get("action") == "publish"
        job = services.create_job(
            client=request.user, skills=skills, publish=publish, **data
        )
        if publish:
            messages.success(
                request,
                f"“{job.title}” is live and {job.budget:,.2f} SkillCoin is reserved "
                "against it.",
            )
        else:
            messages.success(
                request, "Saved as a draft. Publish it when you are ready."
            )
        return redirect(job.get_absolute_url())

    return render(
        request,
        "marketplace/job_form.html",
        {
            "form": form,
            "wallet_info": wallet_summary(request.user),
            "nav": "post_job",
            "page_title": "Post a job",
        },
    )


@client_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def job_edit(request, public_id):
    job = get_object_or_404(
        Job.objects.alive(), public_id=public_id, client=request.user
    )
    form = JobForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        skills = data.pop("skills", None)
        services.update_job(job=job, client=request.user, skills=skills, **data)
        messages.success(request, "Job updated.")
        return redirect(job.get_absolute_url())

    form.fields["skills"].initial = job.skills.all()
    return render(
        request,
        "marketplace/job_form.html",
        {"form": form, "job": job, "nav": "jobs", "page_title": f"Edit {job.title}"},
    )


@client_required
@handle_domain_errors
@require_http_methods(["POST"])
def job_publish(request, public_id):
    job = get_object_or_404(
        Job.objects.alive(), public_id=public_id, client=request.user
    )
    services.publish_job(job=job, client=request.user)
    messages.success(
        request,
        f"“{job.title}” is live. {job.budget:,.2f} SkillCoin is now reserved against it.",
    )
    return redirect(job.get_absolute_url())


@client_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def job_cancel(request, public_id):
    job = get_object_or_404(
        Job.objects.alive(), public_id=public_id, client=request.user
    )
    form = CancelJobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.cancel_job(
            job=job, client=request.user, reason=form.cleaned_data["reason"]
        )
        messages.success(
            request, "Job cancelled and any reserved budget returned to your balance."
        )
        return redirect("marketplace:my_jobs")
    return render(
        request,
        "marketplace/job_cancel.html",
        {"form": form, "job": job, "nav": "jobs", "page_title": "Cancel job"},
    )


@handle_domain_errors
@require_http_methods(["POST"])
def job_save_toggle(request, public_id):
    """Save or unsave a job. Freelancers only; used from the job list."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    job = get_object_or_404(Job.objects.public(), public_id=public_id)
    saved = services.toggle_saved_job(job=job, user=request.user)
    messages.success(
        request, "Job saved." if saved else "Job removed from your saved list."
    )
    return redirect(request.META.get("HTTP_REFERER") or job.get_absolute_url())


def saved_jobs(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    rows = (
        SavedJob.objects.filter(user=request.user)
        .select_related("job", "job__category", "job__client")
        .order_by("-created_at")
    )
    page, querystring = paginate(request, rows, 15)
    return render(
        request,
        "marketplace/saved_jobs.html",
        {
            "page": page,
            "querystring": querystring,
            "nav": "jobs",
            "page_title": "Saved jobs",
        },
    )
