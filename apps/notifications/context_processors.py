"""Notification badge for the signed-in header."""
from __future__ import annotations

def unread(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {"unread_notifications": 0, "recent_notifications": [], "unread_messages_count": 0}
    from apps.notifications.models import Notification
    from apps.messaging.models import ConversationParticipant
    qs = Notification.objects.for_user(user)
    unread_msg = ConversationParticipant.objects.filter(user=user, left_at__isnull=True, unread_count__gt=0).count()
    return {"unread_notifications": qs.unread().count(), "recent_notifications": list(qs.select_related("actor").order_by("-created_at")[:8]), "unread_messages_count": unread_msg}