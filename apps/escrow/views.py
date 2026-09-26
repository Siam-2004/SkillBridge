"""Escrow, seen from the project it belongs to.

Read-only. Funding happens from the agreement, and releases happen from a task
approval or the final project approval — each of which has its own service.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from apps.core.exceptions import PermissionDenied
from apps.core.permissions import verified_required
from apps.core.views import handle_domain_errors
from apps.escrow.models import Escrow


@verified_required
@handle_domain_errors
def detail(request, public_id):
    escrow = get_object_or_404(
        Escrow.objects.select_related("project", "client", "agreement"),
        public_id=public_id,
    )
    project = escrow.project
    if not project.has_access(request.user) and not request.user.is_platform_admin:
        raise PermissionDenied("You do not have access to this project.")

    return render(
        request,
        "escrow/detail.html",
        {
            "escrow": escrow,
            "project": project,
            "allocations": escrow.allocations.select_related(
                "task", "freelancer"
            ).order_by("-created_at"),
            "nav": "projects",
            "page_title": "Escrow",
        },
    )
