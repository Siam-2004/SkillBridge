"""Profiles: dashboards, the public directory, and profile editing."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.permissions import client_required, freelancer_required
from apps.core.views import handle_domain_errors, paginate
from apps.profiles import services
from apps.profiles.forms import (
    ClientProfileForm,
    EducationForm,
    ExperienceForm,
    FreelancerFilterForm,
    FreelancerProfileForm,
    SkillSelectionForm,
)
from apps.profiles.models import (
    Category,
    ClientProfile,
    Education,
    Experience,
    FreelancerProfile,
    Skill,
)
from apps.profiles.selectors import (
    client_public_profile,
    freelancer_public_profile,
    search_freelancers,
)


# --------------------------------------------------------------------------- #
# Public directory
# --------------------------------------------------------------------------- #
def freelancer_list(request):
    """The freelancer directory, with every filter the specification lists."""
    form = FreelancerFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}

    results = search_freelancers(
        keyword=data.get("q") or "",
        category=data.get("category"),
        skills=data.get("skills") or None,
        min_rating=data.get("min_rating"),
        min_reviews=data.get("min_reviews"),
        min_projects=data.get("min_projects"),
        availability=data.get("availability") or "",
        experience_level=data.get("experience_level") or "",
        min_rate=data.get("min_rate"),
        max_rate=data.get("max_rate"),
        has_portfolio=data.get("has_portfolio") or "",
        professional_title=data.get("professional_title") or "",
        sort=data.get("sort") or "rating",
    )
    page, querystring = paginate(request, results, 12)

    return render(
        request,
        "profiles/freelancer_list.html",
        {
            "form": form,
            "page": page,
            "querystring": querystring,
            "total": page.paginator.count,
            "nav_section": "freelancers",
            "page_title": "Find freelancers",
        },
    )


def freelancer_public(request, username: str):
    try:
        profile = freelancer_public_profile(username)
    except FreelancerProfile.DoesNotExist as exc:
        raise Http404("No such freelancer.") from exc
    from apps.portfolios.models import Portfolio

    return render(
        request,
        "profiles/freelancer_public.html",
        {
            "profile": profile,
            "owner": profile.user,
            "skills": profile.skill_entries.select_related("skill"),
            "experiences": profile.experiences.all(),
            "education": profile.education.all(),
            "portfolio": Portfolio.objects.filter(
                freelancer=profile, is_public=True
            ).order_by("order", "-completed_on")[:6],
            "summary": None,
            "reviews": [],
            "nav_section": "freelancers",
            "page_title": profile.user.full_name,
        },
    )


def client_public(request, username: str):
    try:
        profile = client_public_profile(username)
    except ClientProfile.DoesNotExist as exc:
        raise Http404("No such client.") from exc

    return render(
        request,
        "profiles/client_public.html",
        {
            "profile": profile,
            "owner": profile.user,
            "open_jobs": [],
            "summary": None,
            "reviews": [],
            "page_title": profile.user.full_name,
        },
    )


# --------------------------------------------------------------------------- #
# Dashboards
# --------------------------------------------------------------------------- #
@client_required
def client_dashboard(request):
    from apps.wallets.selectors import wallet_summary

    user = request.user

    return render(
        request,
        "profiles/client_dashboard.html",
        {
            "wallet_info": wallet_summary(user),
            "open_jobs": 0,
            "draft_jobs": 0,
            "active_projects": 0,
            "completed_projects": 0,
            "new_proposals": 0,
            "recent_jobs": [],
            "recent_projects": [],
            "awaiting_review": [],
            "nav": "dashboard",
            "page_title": "Dashboard",
        },
    )


@freelancer_required
def freelancer_dashboard(request):
    from apps.wallets.selectors import earnings_breakdown, wallet_summary

    user = request.user

    return render(
        request,
        "profiles/freelancer_dashboard.html",
        {
            "wallet_info": wallet_summary(user),
            "earnings": earnings_breakdown(user),
            "pending_proposals": 0,
            "accepted_proposals": 0,
            "active_projects": 0,
            "open_tasks": [],
            "recent_proposals": [],
            "invitations": [],
            "profile": FreelancerProfile.objects.filter(user=user).first(),
            "nav": "dashboard",
            "page_title": "Dashboard",
        },
    )


# --------------------------------------------------------------------------- #
# Editing
# --------------------------------------------------------------------------- #
@client_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def edit_client(request):
    profile, _ = ClientProfile.objects.get_or_create(user=request.user)
    form = ClientProfileForm(
        request.POST or None, request.FILES or None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        services.update_client_profile(user=request.user, **form.cleaned_data)
        messages.success(request, "Profile saved.")
        return redirect("profiles:edit_client")
    return render(
        request,
        "profiles/edit_client.html",
        {
            "form": form,
            "profile": profile,
            "nav": "profile",
            "page_title": "My profile",
        },
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def edit_freelancer(request):
    profile, _ = FreelancerProfile.objects.get_or_create(user=request.user)
    form = FreelancerProfileForm(
        request.POST or None, request.FILES or None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        services.update_freelancer_profile(user=request.user, **form.cleaned_data)
        messages.success(request, "Profile saved.")
        return redirect("profiles:edit_freelancer")
    return render(
        request,
        "profiles/edit_freelancer.html",
        {
            "form": form,
            "profile": profile,
            "skills": profile.skill_entries.select_related("skill"),
            "experiences": profile.experiences.all(),
            "education": profile.education.all(),
            "nav": "profile",
            "page_title": "My profile",
        },
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def edit_skills(request):
    profile = FreelancerProfile.objects.get(user=request.user)
    if request.method == "POST":
        entries = []
        for skill_id in request.POST.getlist("skill"):
            entries.append(
                {
                    "skill_id": int(skill_id),
                    "level": int(request.POST.get(f"level-{skill_id}") or 2),
                    "years": int(request.POST.get(f"years-{skill_id}") or 0),
                }
            )
        services.set_freelancer_skills(profile=profile, entries=entries)
        profile.categories.set(request.POST.getlist("category"))
        services.reindex_freelancer(profile)
        messages.success(request, "Skills updated.")
        return redirect("profiles:edit_skills")

    return render(
        request,
        "profiles/edit_skills.html",
        {
            "profile": profile,
            "all_skills": Skill.objects.filter(is_active=True).select_related(
                "category"
            ),
            "all_categories": Category.objects.filter(is_active=True),
            "current": {e.skill_id: e for e in profile.skill_entries.all()},
            "current_categories": set(profile.categories.values_list("id", flat=True)),
            "nav": "profile",
            "page_title": "Skills",
        },
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def add_experience(request):
    profile = FreelancerProfile.objects.get(user=request.user)
    form = ExperienceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.add_experience(
            profile=profile, actor=request.user, **form.cleaned_data
        )
        messages.success(request, "Experience added.")
        return redirect("profiles:edit_freelancer")
    return render(
        request,
        "profiles/experience_form.html",
        {"form": form, "nav": "profile", "page_title": "Add experience"},
    )


@freelancer_required
@require_http_methods(["POST"])
def delete_experience(request, pk: int):
    entry = get_object_or_404(Experience, pk=pk, profile__user=request.user)
    entry.delete()
    messages.success(request, "Experience removed.")
    return redirect("profiles:edit_freelancer")


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def add_education(request):
    profile = FreelancerProfile.objects.get(user=request.user)
    form = EducationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.add_education(profile=profile, actor=request.user, **form.cleaned_data)
        messages.success(request, "Education added.")
        return redirect("profiles:edit_freelancer")
    return render(
        request,
        "profiles/education_form.html",
        {"form": form, "nav": "profile", "page_title": "Add education"},
    )


@freelancer_required
@require_http_methods(["POST"])
def delete_education(request, pk: int):
    entry = get_object_or_404(Education, pk=pk, profile__user=request.user)
    entry.delete()
    messages.success(request, "Education removed.")
    return redirect("profiles:edit_freelancer")
