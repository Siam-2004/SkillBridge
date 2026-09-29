"""Conversations.

Messaging is ordinary HTTP: a form post adds a message and the page redirects
back to itself. The conversation page refreshes itself on a timer so an open
window stays current without any realtime infrastructure.
"""
from __future__ import annotations

from django.contrib import messages as flash
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.exceptions import PermissionDenied
from apps.core.permissions import verified_required
from apps.core.views import handle_domain_errors, paginate
from apps.messaging import services
from apps.messaging.forms import MessageForm
from apps.messaging.models import Conversation


def _participant(conversation, user):
    if not conversation.participants.filter(user=user, left_at__isnull=True).exists():
        if not user.is_platform_admin:
            raise PermissionDenied("You are not part of this conversation.")
    return conversation


@verified_required
def conversation_list(request):
    rows = (
        Conversation.objects.for_user(request.user)
        .select_related("job", "agreement", "initiator")
        .prefetch_related("participants__user")
        .distinct()
        .order_by("-last_message_at", "-updated_at")
    )
    page, querystring = paginate(request, rows, 20)
    for c in page.object_list:
        c.counterparty = None
        c.my_unread = 0
        for p in c.participants.all():
            if p.user_id != request.user.pk:
                c.counterparty = p.user
            else:
                c.my_unread = p.unread_count
    return render(request, "messaging/list.html", {
        "page": page,
        "querystring": querystring,
        "nav": "messages",
        "page_title": "Messages",
    })


@verified_required
@handle_domain_errors
def detail(request, public_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related("job", "agreement"), public_id=public_id
    )
    _participant(conversation, request.user)
    services.mark_conversation_read(conversation=conversation, user=request.user)
    return render(request, "messaging/detail.html", {
        "conversation": conversation,
        "messages_list": conversation.messages.select_related("sender").prefetch_related("attachments").order_by("created_at"),
        "participants": conversation.participants.select_related("user").filter(left_at__isnull=True),
        "form": MessageForm(),
        "can_write": conversation.is_writable,
        "nav": "messages",
        "page_title": "Conversation",
    })


@verified_required
@handle_domain_errors
@require_http_methods(["POST"])
def send(request, public_id):
    conversation = get_object_or_404(Conversation, public_id=public_id)
    _participant(conversation, request.user)
    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        flash.error(request, "; ".join(form.errors.get("__all__", ["Message not sent."])))
        return redirect(conversation.get_absolute_url())
    services.send_message(
        conversation=conversation,
        sender=request.user,
        content=form.cleaned_data["content"],
        files=request.FILES.getlist("files"),
    )
    return redirect(conversation.get_absolute_url())


@verified_required
@handle_domain_errors
def poll(request, public_id):
    """Return messages newer than ``after`` so an open window stays current.

    A plain polled endpoint, deliberately: it needs no separate server, and a
    chat that updates every few seconds is indistinguishable from a socket for
    this kind of conversation.
    """
    conversation = get_object_or_404(Conversation, public_id=public_id)
    _participant(conversation, request.user)
    after = request.GET.get("after") or ""
    rows = conversation.messages.select_related("sender").order_by("created_at")
    if after:
        rows = rows.filter(created_at__gt=after)
    return JsonResponse({
        "messages": [{
            "id": str(m.public_id),
            "sender": m.sender.full_name if m.sender else "Skillbridge",
            "username": m.sender.username if m.sender else "",
            "initials": m.sender.initials if m.sender else "SB",
            "is_mine": bool(m.sender_id == request.user.pk),
            "kind": m.kind,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        } for m in rows[:100]]
    })


@verified_required
@handle_domain_errors
@require_http_methods(["POST", "GET"])
def start_job_conversation(request, job_id):
    """Open or view a thread between client and freelancer about a job."""
    from apps.accounts.models import User
    from apps.marketplace.models import Job

    job = get_object_or_404(Job.objects.all(), public_id=job_id)
    freelancer = None
    if request.user.pk == job.client_id:
        freelancer_param = request.POST.get("freelancer") or request.GET.get("freelancer")
        if freelancer_param:
            freelancer = get_object_or_404(User, public_id=freelancer_param)
        elif job.hired_freelancer:
            freelancer = job.hired_freelancer
        else:
            existing = Conversation.objects.filter(job=job).first()
            if existing:
                return redirect(existing.get_absolute_url())
            flash.info(request, "No messages yet for this job.")
            return redirect(job.get_absolute_url())
    else:
        freelancer = request.user
    conversation = services.open_job_conversation(
        job=job, freelancer=freelancer, actor=request.user
    )
    return redirect(conversation.get_absolute_url())