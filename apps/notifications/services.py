"""Notification fan-out.

``notify()`` is called from inside business transactions, so the expensive part
(email, websocket push) is deferred to ``transaction.on_commit()``: a rolled-back
payment must never leave a "payment released" email behind.
"""
from __future__ import annotations
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.notifications.models import Notification, NotificationPreference, NotificationType
logger = logging.getLogger(__name__)


def notify(recipient,kind:str,title:str,*,message:str="",actor=None,target_url:str="",level:str=Notification.Level.INFO,email:bool|None=None,email_template:str="",email_context:dict|None=None,**metadata)->Notification|None:
    """Create one notification, then push and optionally email it after commit."""
    if recipient is None or (actor is not None and actor.pk == recipient.pk):
        # Never notify somebody about their own action.
        return None
    note=Notification.objects.create(recipient=recipient,actor=actor,notification_type=kind,level=level,title=title[:180],message=message[:500],target_url=target_url[:500],metadata=_clean(metadata))
    if email is None:
        prefs,_=NotificationPreference.objects.get_or_create(user=recipient)
        email=prefs.allows_email(kind)
    if email:
        transaction.on_commit(lambda:_email(note,email_template,email_context or {}))
    return note


def notify_many(*recipients,kind:str,title:str,**kwargs)->list[Notification]:
    seen:set[int]=set();created=[]
    for recipient in recipients:
        if recipient is None or recipient.pk in seen: continue
        seen.add(recipient.pk);note=notify(recipient,kind,title,**kwargs)
        if note: created.append(note)
    return created


def mark_read(user,*,public_ids=None)->int:
    qs=Notification.objects.for_user(user).unread()
    if public_ids: qs=qs.filter(public_id__in=public_ids)
    return qs.update(read_at=timezone.now())


def unread_count(user)->int:
    if not(user and user.is_authenticated): return 0
    return Notification.objects.for_user(user).unread().count()


# --------------------------------------------------------------------------- #
# Delivery
#
# In-app notifications are rows; the badge and the list read them. Email is
# best-effort: a mail server having a bad minute must not roll back a payment
# that has already happened, so failures are logged, never raised.
# --------------------------------------------------------------------------- #
def _email(note:Notification,template:str,context:dict):
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        template=template or "emails/notification.html"
        ctx={"note":note,"recipient":note.recipient,"skillcoin":settings.SKILLCOIN,**context}
        html=render_to_string(template,ctx);text=render_to_string("emails/notification.txt",ctx)
        mail=EmailMultiAlternatives(subject=f"[Skillbridge] {note.title}",body=text,to=[note.recipient.email])
        mail.attach_alternative(html,"text/html");mail.send(fail_silently=False)
        Notification.objects.filter(pk=note.pk).update(emailed_at=timezone.now())
    except Exception: # pragma: no cover
        logger.warning("notification email failed id=%s",note.public_id,exc_info=True)


def _clean(metadata:dict)->dict:
    from decimal import Decimal
    from uuid import UUID
    def _convert(v):
        if isinstance(v,(Decimal,UUID)): return str(v)
        if isinstance(v,dict): return {str(k):_convert(val) for k,val in v.items()}
        if isinstance(v,(list,tuple,set)): return [_convert(val) for val in v]
        return v
    try: return {str(k):_convert(v) for k,v in (metadata or {}).items()}
    except Exception: return {}


__all__=["notify","notify_many","mark_read","unread_count","NotificationType"]