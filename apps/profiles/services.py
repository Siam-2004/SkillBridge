"""Profile editing and freelancer search indexing."""

from __future__ import annotations

from django.db import transaction

from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.core.money import to_coin
from apps.core.validators import validate_bd_phone, validate_url
from apps.profiles.models import (
    ClientProfile,
    Education,
    Experience,
    FreelancerProfile,
    FreelancerSkill,
)

CLIENT_FIELDS = {
    "bio",
    "company_name",
    "company_description",
    "company_size",
    "industry",
    "phone",
    "location",
    "website",
}
FREELANCER_FIELDS = {
    "professional_title",
    "bio",
    "phone",
    "location",
    "website",
    "github_url",
    "linkedin_url",
    "availability",
    "experience_level",
    "years_experience",
    "languages",
    "is_available_for_hire",
}


@transaction.atomic()
def update_client_profile(*, user, **fields) -> ClientProfile:
    profile, _ = ClientProfile.objects.get_or_create(user=user)
    for key, value in fields.items():
        if key not in CLIENT_FIELDS:
            continue
        if key == "phone":
            value = validate_bd_phone(value)
        elif key == "website":
            value = validate_url(value)
        setattr(profile, key, value)
    profile.is_profile_complete = profile.completeness >= 70
    profile.save()
    reindex_client(profile)
    return profile


@transaction.atomic()
def update_freelancer_profile(*, user, hourly_rate=None, **fields) -> FreelancerProfile:
    profile, _ = FreelancerProfile.objects.get_or_create(user=user)
    for key, value in fields.items():
        if key not in FREELANCER_FIELDS:
            continue
        if key == "phone":
            value = validate_bd_phone(value)
        elif key in {"website", "github_url", "linkedin_url"}:
            value = validate_url(value)
        setattr(profile, key, value)
    if hourly_rate not in (None, ""):
        rate = to_coin(hourly_rate)
        if rate < 0:
            raise ValidationFailed("An hourly rate cannot be negative.")
        profile.hourly_rate = rate
    profile.is_profile_complete = profile.completeness >= 70
    profile.save()
    reindex_freelancer(profile)
    return profile


@transaction.atomic()
def set_freelancer_skills(*, profile: FreelancerProfile, entries: list[dict]):
    """Replace the skill list.

    ``entries`` is ``[{"skill": Skill | "skill_id": int, "level": int,
    "years": int, "is_primary": bool}, ...]``.
    """
    if len(entries) > 40:
        raise ValidationFailed("List up to 40 skills.")
    FreelancerSkill.objects.filter(profile=profile).delete()
    rows = [
        FreelancerSkill(
            profile=profile,
            skill=entry.get("skill"),
            skill_id=entry.get("skill_id") or getattr(entry.get("skill"), "pk", None),
            level=int(entry.get("level", FreelancerSkill.Level.INTERMEDIATE)),
            years=int(entry.get("years", 0) or 0),
            is_primary=bool(entry.get("is_primary")),
        )
        for entry in entries
    ]
    FreelancerSkill.objects.bulk_create(rows)
    # Skill.usage_count is rebuilt from scratch by
    # `manage.py recompute_metrics` — incrementing it here would drift every
    # time a freelancer edits their skill list.

    profile.is_profile_complete = profile.completeness >= 70
    profile.save(update_fields=["is_profile_complete", "updated_at"])
    reindex_freelancer(profile)
    return rows


@transaction.atomic()
def add_experience(*, profile: FreelancerProfile, actor, **fields) -> Experience:
    if actor.pk != profile.user_id:
        raise PermissionDenied("You can only edit your own profile.")
    if not fields.get("position") or not fields.get("company"):
        raise ValidationFailed("A position and company are required.")
    if (
        fields.get("end_date")
        and fields.get("start_date")
        and (fields["end_date"] < fields["start_date"])
    ):
        raise ValidationFailed("The end date cannot be before the start date.")
    experience = Experience.objects.create(profile=profile, **fields)
    reindex_freelancer(profile)
    return experience


@transaction.atomic()
def add_education(*, profile: FreelancerProfile, actor, **fields) -> Education:
    if actor.pk != profile.user_id:
        raise PermissionDenied("You can only edit your own profile.")
    if not fields.get("institution") or not fields.get("degree"):
        raise ValidationFailed("An institution and degree are required.")
    end_date = fields.get("end_date")
    if end_date and fields.get("start_date") and end_date < fields["start_date"]:
        raise ValidationFailed("The end date cannot be before the start date.")
    education = Education.objects.create(profile=profile, **fields)
    reindex_freelancer(profile)
    return education


def reindex_freelancer(profile: FreelancerProfile) -> None:
    """Refresh the searchable text for one freelancer.

    Name, title and skills are repeated so that searching "Django" ranks
    somebody whose skill is Django above somebody who merely mentioned it in a
    sentence.
    """
    from apps.core.search import build_search_text

    skills = " ".join(profile.skills.values_list("name", flat=True))
    categories = " ".join(profile.categories.values_list("name", flat=True))
    experience = " ".join(
        f"{e.position} {e.company} {e.description}"
        for e in profile.experiences.all()[:10]
    )
    FreelancerProfile.objects.filter(pk=profile.pk).update(
        search_text=build_search_text(
            profile.user.full_name,
            profile.professional_title,
            profile.professional_title,
            skills,
            skills,
            categories,
            profile.location,
            profile.bio,
            experience,
        )
    )


def reindex_client(profile: ClientProfile) -> None:
    """Refresh the searchable text for one client."""
    from apps.core.search import build_search_text

    ClientProfile.objects.filter(pk=profile.pk).update(
        search_text=build_search_text(
            profile.user.full_name,
            profile.company_name,
            profile.company_name,
            profile.industry,
            profile.location,
            profile.bio,
            profile.company_description,
        )
    )
