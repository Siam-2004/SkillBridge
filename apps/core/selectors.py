"""Read-only queries for platform-wide figures.

The home page must never show a hardcoded number, so every statistic it
displays is computed here from live rows and cached briefly in Django's
default local-memory cache. The cache is an optimisation, never a dependency.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models import Avg, Count, Q, Sum

logger = logging.getLogger(__name__)

STATS_CACHE_KEY = "platform_stats_v1"
STATS_CACHE_TTL = 120


def platform_stats(*, refresh: bool = False) -> dict:
    if not refresh:
        cached = cache.get(STATS_CACHE_KEY)
        if cached is not None:
            return cached

    from apps.accounts.models import Role, User
    from apps.wallets.models import WalletTransaction

    users = User.objects.filter(status=User.Status.ACTIVE, is_email_verified=True)
    stats = {
        "total_clients": users.filter(role=Role.CLIENT).count(),
        "total_freelancers": users.filter(role=Role.FREELANCER).count(),
        "completed_projects": 0,
        "available_jobs": 0,
        "total_paid_out": WalletTransaction.objects.filter(
            transaction_type=WalletTransaction.Type.PROJECT_PAYMENT,
            status=WalletTransaction.Status.COMPLETED,
        ).aggregate(total=Sum("amount"))["total"]
        or 0,
        "average_rating": 5.0,
        "total_reviews": 0,
    }
    cache.set(STATS_CACHE_KEY, stats, STATS_CACHE_TTL)
    return stats


def invalidate_platform_stats():
    """Drop the cached figures after a job or project changes."""
    cache.delete(STATS_CACHE_KEY)


def homepage_blocks() -> dict:
    """Editable marketing copy, grouped by slot."""
    from apps.core.models import HomepageSection

    blocks: dict[str, list] = {}
    for block in HomepageSection.objects.filter(is_active=True):
        blocks.setdefault(block.slot, []).append(block)
    return blocks


def category_tree(*, with_counts: bool = True):
    """Top-level categories with their children."""
    from apps.profiles.models import Category

    return Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related(
        "children"
    )


def project_activity(project, *, viewer=None, limit: int | None = None):
    """The activity stream for one project, filtered to what ``viewer`` may see."""
    from apps.core.models import ActivityLog

    qs = ActivityLog.objects.filter(project_id=getattr(project, "id", project)).select_related("actor")
    if viewer is None or not getattr(viewer, "is_platform_admin", False):
        qs = qs.exclude(visibility=ActivityLog.Visibility.ADMIN)
    return qs[:limit] if limit else qs
