from __future__ import annotations
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.core.exceptions import InvalidState, PermissionDenied, ValidationFailed
from apps.core.permissions import require_verified
from apps.messaging.models import Conversation, ConversationParticipant, Message, MessageAttachment, MessageReceipt
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
Role = ConversationParticipant.Role

@transaction.atomic()
def open_job_conversation(*, job, freelancer=None, actor=None) -> Conversation:
    actor = actor or freelancer
    if not actor:
        raise ValidationFailed('Actor is required.')
    require_verified(actor)
    if actor.pk == job.client_id:
        if not freelancer:
            raise ValidationFailed('Select a freelancer to message.')
    else:
        freelancer = actor
    require_verified(freelancer)
    if job.client_id == freelancer.pk:
        raise PermissionDenied('You cannot start a conversation with yourself.')
    existing = Conversation.objects.filter(job=job, participants__user=freelancer).first()
    if existing:
        return existing
    conversation = Conversation.objects.create(conversation_type=Conversation.Kind.JOB, subject=job.title[:200], job=job, initiator=actor)
    ConversationParticipant.objects.bulk_create([ConversationParticipant(conversation=conversation, user=job.client, role=Role.CLIENT), ConversationParticipant(conversation=conversation, user=freelancer, role=Role.FREELANCER)])
    return conversation

@transaction.atomic()
def open_project_conversation(*, project, actor=None) -> Conversation:
    existing = Conversation.objects.filter(project=project, conversation_type=Conversation.Kind.PROJECT).first()
    if existing:
        return existing
    conversation = Conversation.objects.create(conversation_type=Conversation.Kind.PROJECT, subject=project.title[:200], job=project.job, project=project, initiator=actor)
    ConversationParticipant.objects.bulk_create([ConversationParticipant(conversation=conversation, user=project.client, role=Role.CLIENT), ConversationParticipant(conversation=conversation, user=project.freelancer, role=Role.TEAM_OWNER)])
    send_system_message(conversation=conversation, content=f'Project workspace opened. Escrow of {project.final_price:,.2f} SKC is held for this project.')
    return conversation

@transaction.atomic()
def add_project_participant(*, project, user, role: str=Role.TEAM_MEMBER):
    conversation = open_project_conversation(project=project)
    participant, created = ConversationParticipant.objects.get_or_create(conversation=conversation, user=user, defaults={'role': role})
    if not created and participant.left_at:
        participant.left_at = None
        participant.joined_at = timezone.now()
        participant.save(update_fields=['left_at', 'joined_at', 'updated_at'])
    if created:
        send_system_message(conversation=conversation, content=f'{user.full_name} joined the project.')
    return participant

@transaction.atomic()
def remove_project_participant(*, project, user):
    conversation = Conversation.objects.filter(project=project, conversation_type=Conversation.Kind.PROJECT).first()
    if not conversation:
        return None
    updated = ConversationParticipant.objects.filter(conversation=conversation, user=user, left_at__isnull=True).update(left_at=timezone.now())
    if updated:
        send_system_message(conversation=conversation, content=f'{user.full_name} left the project.')
    return updated

@transaction.atomic()
def send_message(*, conversation: Conversation, sender, content: str='', files=None) -> Message:
    require_verified(sender)
    conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
    participant = ConversationParticipant.objects.filter(conversation=conversation, user=sender, left_at__isnull=True).first()
    if not participant:
        raise PermissionDenied('You are not a participant in this conversation.')
    if not conversation.is_writable:
        raise InvalidState('This conversation is archived. It stays readable and searchable, but new messages cannot be sent.')
    if not content.strip() and (not files):
        raise ValidationFailed('Write a message or attach a file.')
    message = Message.objects.create(conversation=conversation, sender=sender, kind=Message.Kind.FILE if files and (not content.strip()) else Message.Kind.TEXT, content=content.strip()[:8000], delivered_at=timezone.now())
    for upload in files or []:
        MessageAttachment.objects.create(message=message, file=upload, original_name=getattr(upload, 'name', 'file')[:255], size_bytes=getattr(upload, 'size', 0) or 0, content_type=getattr(upload, 'content_type', '')[:120])
        if message.kind == Message.Kind.TEXT and (not message.content):
            message.kind = Message.Kind.FILE
            message.save(update_fields=['kind'])
    mentioned = _resolve_mentions(content, conversation)
    if mentioned:
        message.mentions.set(mentioned)
    _touch_conversation(conversation, message)
    _notify_recipients(conversation, message, mentioned)
    if conversation.job_id:
        from apps.marketplace.models import Job
        Job.objects.filter(pk=conversation.job_id).update(message_count=F('message_count') + 1)
    record_activity(ActivityVerb.MESSAGE_SENT, f"Sent a message in “{conversation.subject or 'conversation'}”", actor=sender, job=conversation.job, target=message, visibility='ADMIN_ONLY')
    return message

@transaction.atomic()
def send_system_message(*, conversation: Conversation, content: str) -> Message:
    message = Message.objects.create(conversation=conversation, sender=None, kind=Message.Kind.SYSTEM, content=content[:8000], delivered_at=timezone.now())
    _touch_conversation(conversation, message)
    return message

@transaction.atomic()
def mark_conversation_read(*, conversation: Conversation, user) -> int:
    participant = ConversationParticipant.objects.filter(conversation=conversation, user=user).first()
    if not participant:
        return 0
    unread = conversation.messages.exclude(sender=user).exclude(receipts__user=user)
    receipts = [MessageReceipt(message=m, user=user) for m in unread]
    MessageReceipt.objects.bulk_create(receipts, ignore_conflicts=True)
    participant.last_read_at = timezone.now()
    participant.unread_count = 0
    participant.save(update_fields=['last_read_at', 'unread_count', 'updated_at'])
    return len(receipts)

@transaction.atomic()
def archive_project_conversations(*, project, reason: str='') -> int:
    conversations = Conversation.objects.filter(project=project, status=Conversation.Status.ACTIVE)
    for conversation in conversations:
        send_system_message(conversation=conversation, content=f'Conversation archived. {reason} This history remains available for reference, audit and dispute evidence.')
    count = conversations.update(status=Conversation.Status.ARCHIVED, archived_at=timezone.now(), archive_reason=reason[:200])
    Conversation.objects.filter(job=project.job, conversation_type=Conversation.Kind.JOB, status=Conversation.Status.ACTIVE).update(status=Conversation.Status.ARCHIVED, archived_at=timezone.now(), archive_reason='Job completed.')
    if count:
        record_activity(ActivityVerb.CONVERSATION_ARCHIVED, 'Project conversations archived', project=project, visibility='PARTICIPANTS')
    return count

def _touch_conversation(conversation: Conversation, message: Message) -> None:
    Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at, last_message_preview=message.preview[:200], message_count=F('message_count') + 1)
    ConversationParticipant.objects.filter(conversation=conversation, left_at__isnull=True).exclude(user=message.sender).update(unread_count=F('unread_count') + 1)
    _reindex_message(message)

def _reindex_message(message: Message) -> None:
    from apps.core.search import build_search_text
    if not message.content:
        return
    Message.objects.filter(pk=message.pk).update(search_text=build_search_text(message.content))

def _resolve_mentions(text: str, conversation: Conversation):
    import re
    handles = {m.lower() for m in re.findall('@([\\w.-]{2,50})', text or '')}
    if not handles:
        return []
    return [u for u in conversation.participant_users() if u.username.lower() in handles]

def _notify_recipients(conversation: Conversation, message: Message, mentioned) -> None:
    mentioned_ids = {u.pk for u in mentioned}
    for user in conversation.participant_users():
        if user.pk == (message.sender_id or 0):
            continue
        is_mention = user.pk in mentioned_ids
        notify(user, NotificationType.MENTION if is_mention else NotificationType.NEW_MESSAGE, f'{message.sender.full_name} mentioned you' if is_mention else f'New message from {message.sender.full_name}', message=message.preview, actor=message.sender, target_url=_conversation_url(conversation, user))

def _conversation_url(conversation: Conversation, user=None) -> str:
    return f'/messages/{conversation.public_id}/'
