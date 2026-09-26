"""Portfolio management."""

from __future__ import annotations

from django.db import transaction
from django.db.models import F

from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.core.validators import validate_image, validate_url
from apps.portfolios.models import Portfolio, PortfolioMedia, PortfolioView

ITEM_FIELDS = {
    "title",
    "description",
    "demo_url",
    "repository_url",
    "technologies",
    "tech_stack",
    "role",
    "responsibilities",
    "outcome",
    "duration_months",
    "completed_on",
    "client_name",
    "tags",
    "is_public",
    "is_featured",
    "confidentiality_note",
    "category",
}


@transaction.atomic()
def create_item(
    *,
    profile,
    actor,
    title: str,
    description: str,
    skills=None,
    cover_image=None,
    **fields,
) -> Portfolio:
    if actor.pk != profile.user_id:
        raise PermissionDenied("You can only edit your own portfolio.")
    if not title.strip():
        raise ValidationFailed("Give the project a title.")
    if not description.strip():
        raise ValidationFailed("Describe what the project involved.")

    clean = {k: v for k, v in fields.items() if k in ITEM_FIELDS}
    for key in ("demo_url", "repository_url"):
        if clean.get(key):
            clean[key] = validate_url(clean[key])

    order = Portfolio.objects.filter(freelancer=profile).count() + 1
    item = Portfolio.objects.create(
        freelancer=profile,
        title=title.strip()[:200],
        description=description.strip(),
        order=order,
        **clean,
    )
    if cover_image is not None:
        item.cover_image = validate_image(cover_image)
        item.save(update_fields=["cover_image"])
    if skills:
        item.skills.set(skills)

    reindex_item(item)
    from apps.profiles.services import reindex_freelancer

    reindex_freelancer(profile)
    return item


@transaction.atomic()
def update_item(*, item: Portfolio, actor, skills=None, cover_image=None, **fields):
    if actor.pk != item.freelancer.user_id:
        raise PermissionDenied("You can only edit your own portfolio.")
    for key, value in fields.items():
        if key not in ITEM_FIELDS:
            continue
        if key in {"demo_url", "repository_url"} and value:
            value = validate_url(value)
        setattr(item, key, value)
    if cover_image is not None:
        item.cover_image = validate_image(cover_image)
    item.save()
    if skills is not None:
        item.skills.set(skills)
    reindex_item(item)
    return item


@transaction.atomic()
def delete_item(*, item: Portfolio, actor) -> None:
    if actor.pk != item.freelancer.user_id and not actor.is_platform_admin:
        raise PermissionDenied("You can only remove your own portfolio items.")
    item.delete()


@transaction.atomic()
def add_media(
    *,
    item: Portfolio,
    actor,
    image,
    kind=PortfolioMedia.Kind.SCREENSHOT,
    caption: str = "",
    alt_text: str = "",
) -> PortfolioMedia:
    if actor.pk != item.freelancer.user_id:
        raise PermissionDenied("You can only edit your own portfolio.")
    if item.media.count() >= 12:
        raise ValidationFailed("A portfolio item can hold up to 12 images.")
    validate_image(image)
    return PortfolioMedia.objects.create(
        item=item,
        image=image,
        kind=kind,
        caption=caption[:200],
        alt_text=(alt_text or caption or item.title)[:200],
    )


@transaction.atomic()
def create_from_project(*, project, freelancer) -> Portfolio:
    """Turn a delivered Skillbridge project into a verified portfolio entry.

    Client identity is deliberately *not* copied: forbids publishing
    confidential project data, so the item starts private with the client name
    blank, and the freelancer decides what is safe to publish.
    """
    from apps.profiles.models import FreelancerProfile

    if project.status != project.Status.COMPLETED:
        raise ValidationFailed("Only a completed project can become a portfolio entry.")
    if not project.has_access(freelancer):
        raise PermissionDenied("You did not work on this project.")

    profile = FreelancerProfile.objects.get(user=freelancer)
    existing = Portfolio.objects.filter(
        freelancer=profile, source_project=project
    ).first()
    if existing:
        return existing

    item = Portfolio.objects.create(
        freelancer=profile,
        title=project.title[:200],
        description=project.description or project.agreement.deliverables,
        category=project.job.category,
        role="Team owner" if freelancer.pk == project.freelancer_id else "Team member",
        outcome="Delivered and approved on Skillbridge.",
        completed_on=project.completed_at.date if project.completed_at else None,
        source_project=project,
        is_public=False,
        confidentiality_note="Client details withheld pending permission.",
        order=Portfolio.objects.filter(freelancer=profile).count() + 1,
    )
    item.skills.set(project.job.skills.all())
    reindex_item(item)
    return item


@transaction.atomic()
def record_item_view(*, item: Portfolio, user=None, session_key: str = "") -> None:
    if not user and not session_key:
        return
    _, created = PortfolioView.objects.get_or_create(
        portfolio=item,
        user=user if (user and user.is_authenticated) else None,
        session_key="" if (user and user.is_authenticated) else session_key[:60],
    )
    if created:
        Portfolio.objects.filter(pk=item.pk).update(view_count=F("view_count") + 1)


def reindex_item(item: Portfolio) -> None:
    """Refresh the searchable text for one portfolio item."""
    from apps.core.search import build_search_text

    skills = " ".join(item.skills.values_list("name", flat=True))
    Portfolio.objects.filter(pk=item.pk).update(
        search_text=build_search_text(
            item.title,
            item.title,
            skills,
            skills,
            item.technologies,
            item.tech_stack,
            item.tags,
            item.description,
            item.role,
            item.responsibilities,
            item.outcome,
        )
    )
