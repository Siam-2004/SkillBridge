"""Activity recording.

Every important state change writes one row here so that a project's history
reads as a narrative. Sensitive actions additionally write to ``apps.audit``.
"""

from __future__ import annotations

from apps.core.middleware import current_actor
from apps.core.models import ActivityLog


def record_activity(
    action: str,
    description: str,
    *,
    actor=None,
    job=None,
    project=None,
    task=None,
    target=None,
    target_url: str = "",
    visibility: str = ActivityLog.Visibility.PARTICIPANTS,
    **metadata,
) -> ActivityLog:
    """Write one activity row.

    ``actor`` falls back to whoever is handling the current request, so a
    service three layers deep does not need the caller to thread it through.
    """
    if actor is None:
        actor = current_actor()

    object_type = target.__class__.__name__ if target is not None else ""
    object_id = ""
    if target is not None:
        object_id = str(getattr(target, "public_id", "") or target.pk)
    if not target_url and target is not None and hasattr(target, "get_absolute_url"):
        try:
            target_url = target.get_absolute_url()
        except Exception:
            target_url = ""

    return ActivityLog.objects.create(
        actor=actor,
        action=action,
        description=description[:400],
        object_type=object_type,
        object_id=object_id,
        target_url=target_url[:400],
        job_id=getattr(job, "id", job) if job else None,
        project_id=getattr(project, "id", project) if project else None,
        task_id=getattr(task, "id", task) if task else None,
        visibility=visibility,
        metadata=_jsonable(metadata),
    )


def _jsonable(data):
    """Normalise model instances and Decimals so the JSON column stays valid."""
    from decimal import Decimal

    def convert(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [convert(v) for v in value]
        if hasattr(value, "public_id"):
            return str(value.public_id)
        if hasattr(value, "pk"):
            return str(value.pk)
        return str(value)

    return {key: convert(val) for key, val in (data or {}).items()}


def get_setting(key: str, default=None):
    """Read a ``SiteSetting``, falling back to ``default`` if unset."""
    from apps.core.models import SiteSetting

    setting = SiteSetting.objects.filter(key=key).first()
    return setting.typed_value if setting else default
