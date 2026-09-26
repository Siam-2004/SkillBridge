from __future__ import annotations

from django.db.models import Q

from apps.core.search import relevance, text_filter
from apps.portfolios.models import Portfolio


def public_items_for(username: str):
    return (
        Portfolio.objects.filter(freelancer__user__username=username, is_public=True)
        .select_related("category")
        .prefetch_related("media", "skills")
        .order_by("-is_featured", "order")
    )


def item_detail(username: str, public_id, *, viewer=None) -> Portfolio:
    item = (
        Portfolio.objects.select_related(
            "freelancer__user", "category"
        )
        .prefetch_related("media", "skills")
        .get(freelancer__user__username=username, public_id=public_id)
    )
    if not item.is_public:
        owner_id = item.freelancer.user_id
        if not viewer or not viewer.is_authenticated:
            raise Portfolio.DoesNotExist
        if viewer.pk != owner_id and not viewer.is_platform_admin:
            raise Portfolio.DoesNotExist
    return item


def search_portfolio(keyword: str, *, limit: int = 20):
    """Powers global search and the assistant's portfolio lookups."""
    qs = Portfolio.objects.filter(is_public=True).select_related(
        "freelancer__user", "category"
    )
    keyword = (keyword or "").strip()
    if not keyword:
        return qs.none()
    return (
        qs.filter(text_filter(keyword, "search_text"))
        .annotate(rank=relevance(keyword, "title"))
        .order_by("-rank", "-completed_on")[:limit]
    )
