"""Freelancer and client search."""

from __future__ import annotations

from django.db.models import Q

from apps.core.money import to_coin
from apps.core.search import relevance, text_filter
from apps.profiles.models import ClientProfile, FreelancerProfile

SORT_OPTIONS = {
    "rating": ("-completed_projects", "Most projects delivered"),
    "reviews": ("-completed_projects", "Most projects delivered"),
    "projects": ("-completed_projects", "Most projects delivered"),
    "rate_low": ("hourly_rate", "Lowest rate"),
    "rate_high": ("-hourly_rate", "Highest rate"),
    "newest": ("-created_at", "Newest members"),
    "relevance": ("-rank", "Best match"),
}


def search_freelancers(
    *,
    keyword: str = "",
    skills=None,
    category=None,
    min_rating=None,
    min_reviews=None,
    min_projects=None,
    availability: str = "",
    experience_level: str = "",
    max_rate=None,
    min_rate=None,
    has_portfolio: str = "",
    professional_title: str = "",
    sort: str = "projects",
):
    """the freelancer directory, with every filter the spec lists."""
    qs = (
        FreelancerProfile.objects.filter(
            user__status="ACTIVE", user__is_email_verified=True
        )
        .select_related("user")
        .prefetch_related("skill_entries__skill", "categories")
    )

    if keyword:
        keyword = keyword.strip()
        qs = qs.filter(text_filter(keyword, "search_text")).annotate(
            rank=relevance(keyword, "professional_title")
        )
    elif sort == "relevance":
        sort = "projects"

    if skills:
        qs = qs.filter(skills__in=skills).distinct()
    if category:
        qs = qs.filter(
            Q(categories=category) | Q(categories__parent=category)
        ).distinct()
    if min_projects not in (None, ""):
        qs = qs.filter(completed_projects__gte=int(min_projects))
    if availability:
        qs = qs.filter(availability=availability)
    if experience_level:
        qs = qs.filter(experience_level=experience_level)
    if min_rate not in (None, ""):
        qs = qs.filter(hourly_rate__gte=to_coin(min_rate))
    if max_rate not in (None, ""):
        qs = qs.filter(hourly_rate__lte=to_coin(max_rate))
    if has_portfolio == "yes":
        qs = qs.filter(portfolio_items__is_public=True).distinct()
    if professional_title:
        qs = qs.filter(professional_title__icontains=professional_title)

    order, _ = SORT_OPTIONS.get(sort, SORT_OPTIONS["projects"])
    if order == "-rank" and keyword and len(keyword) >= 3:
        return qs.order_by("-rank", "-completed_projects")
    return qs.order_by(order, "-completed_projects", "-id")


def featured_freelancers(limit: int = 8):
    """Home page freelancer cards — proven delivery first."""
    return (
        FreelancerProfile.objects.filter(
            user__status="ACTIVE",
            user__is_email_verified=True,
            is_available_for_hire=True,
        )
        .select_related("user")
        .prefetch_related("skill_entries__skill")
        .order_by(
            "-completed_projects",
            "-created_at",
        )[:limit]
    )


def freelancer_public_profile(username: str) -> FreelancerProfile:
    return (
        FreelancerProfile.objects.select_related("user")
        .prefetch_related(
            "skill_entries__skill",
            "categories",
            "experiences",
            "education",
            "portfolio_items__media",
        )
        .get(user__username=username, user__status="ACTIVE")
    )


def client_public_profile(username: str) -> ClientProfile:
    return ClientProfile.objects.select_related("user").get(
        user__username=username, user__status="ACTIVE"
    )
