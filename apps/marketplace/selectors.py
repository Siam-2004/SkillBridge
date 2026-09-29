"""Job search and filtering.

Search runs entirely through the Django ORM against a denormalised
``search_text`` column, so it behaves identically on every machine and needs no
search server. Ranking floats title matches above body matches.
"""

from __future__ import annotations

from django.db.models import Count, Q

from apps.core.money import to_coin
from apps.core.search import relevance, text_filter
from apps.marketplace.models import Job

SORT_OPTIONS = {
    "newest": ("-published_at", "Newest first"),
    "oldest": ("published_at", "Oldest first"),
    "budget_high": ("-budget", "Highest budget"),
    "budget_low": ("budget", "Lowest budget"),
    "deadline": ("deadline", "Closest deadline"),
    "proposals": ("-proposal_count", "Most proposals"),
    "least_proposals": ("proposal_count", "Fewest proposals"),
    "relevance": ("-rank", "Best match"),
}


def search_jobs(
    *,
    keyword: str = "",
    category=None,
    skills=None,
    min_budget=None,
    max_budget=None,
    deadline_before=None,
    experience_level: str = "",
    job_type: str = "",
    complexity: str = "",
    people: str = "",
    team_required: str = "",
    status: str = "",
    sort: str = "newest",
    viewer=None,
):
    qs = (
        Job.objects.open_to_proposals()
        .filter(hired_freelancer__isnull=True)
        .exclude(agreements__status__in=["ACTIVE", "IN_PROGRESS", "COMPLETED"])
        .select_related("client", "category")
        .prefetch_related("skills")
    )

    if status and status in Job.OPEN_STATUSES:
        qs = qs.filter(status=status)

    if keyword:
        keyword = keyword.strip()
        qs = qs.filter(text_filter(keyword, "search_text")).annotate(
            rank=relevance(keyword, "title")
        )
    elif sort == "relevance":
        sort = "newest"

    if category:
        # Include child categories so "Development" also returns "Backend".
        qs = qs.filter(Q(category=category) | Q(category__parent=category))
    if skills:
        qs = qs.filter(skills__in=skills).distinct()
    if min_budget not in (None, ""):
        qs = qs.filter(budget__gte=to_coin(min_budget))
    if max_budget not in (None, ""):
        qs = qs.filter(budget__lte=to_coin(max_budget))
    if deadline_before:
        qs = qs.filter(deadline__lte=deadline_before)
    if experience_level:
        qs = qs.filter(experience_level=experience_level)
    if job_type:
        qs = qs.filter(job_type=job_type)
    if complexity:
        qs = qs.filter(complexity=complexity)

    # "single freelancer" / "multiple freelancers" filters.
    if people == "single":
        qs = qs.filter(people_required=1)
    elif people == "multiple":
        qs = qs.filter(people_required__gt=1)
    if team_required == "yes":
        qs = qs.filter(team_required=True)
    elif team_required == "no":
        qs = qs.filter(team_required=False)

    order, _ = SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])
    if order == "-rank" and keyword and len(keyword) >= 3:
        return qs.order_by("-rank", "-published_at")
    return qs.order_by(order, "-id")


def featured_jobs(limit: int = 6):
    """Home page job cards — featured first, then freshest."""
    return (
        Job.objects.open_to_proposals()
        .select_related("client", "category")
        .prefetch_related("skills")
        .order_by("-is_featured", "-published_at")[:limit]
    )


def similar_jobs(job: Job, limit: int = 4):
    """Same category or overlapping skills, excluding the job itself."""
    skill_ids = list(job.skills.values_list("id", flat=True))
    return (
        Job.objects.open_to_proposals()
        .exclude(pk=job.pk)
        .filter(Q(category=job.category) | Q(skills__in=skill_ids))
        .select_related("category", "client")
        .annotate(shared=Count("skills", filter=Q(skills__in=skill_ids)))
        .order_by("-shared", "-published_at")
        .distinct()[:limit]
    )


def client_jobs(client, *, status: str = "", search: str = ""):
    qs = (
        Job.objects.for_client(client)
        .select_related("category")
        .prefetch_related("skills")
        .annotate(
            live_proposals=Count(
                "proposals",
                filter=Q(
                    proposals__status__in=[
                        "SUBMITTED",
                        "UNDER_REVIEW",
                        "NEGOTIATING",
                    ]
                ),
            )
        )
    )
    if status == "active":
        qs = qs.filter(status__in=Job.OPEN_STATUSES)
    elif status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    return qs.order_by("-created_at")


def job_detail(public_id, *, viewer=None):
    """One job with everything the detail page needs."""
    qs = Job.objects.alive().select_related("client", "category", "hired_freelancer")
    job = qs.prefetch_related("skills", "attachments").get(public_id=public_id)
    # A draft or cancelled job is visible only to its owner and to admins.
    if not job.is_public:
        if not viewer or not viewer.is_authenticated:
            raise Job.DoesNotExist
        if viewer.pk != job.client_id and not viewer.is_platform_admin:
            raise Job.DoesNotExist
    return job
