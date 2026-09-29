"""Notification list and read-state endpoints."""
from __future__ import annotations
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from apps.core.views import paginate, wants_json
from apps.notifications.models import Notification
from apps.notifications.services import mark_read, unread_count


def notification_list(request):
    if not request.user.is_authenticated: return redirect("accounts:login")
    qs=Notification.objects.for_user(request.user).select_related("actor")
    unread_only=request.GET.get("filter")=="unread"
    if unread_only: qs=qs.unread()
    page,querystring=paginate(request,qs,per_page=25)
    return render(request,"notifications/list.html",{"page_obj":page,"querystring":querystring,"unread_only":unread_only,"unread":unread_count(request.user),"nav":"notifications","page_title":"Notifications"})


@require_http_methods(["POST"])
def read_all(request):
    if not request.user.is_authenticated: return JsonResponse({"detail":"Authentication required."},status=401)
    count=mark_read(request.user)
    if wants_json(request): return JsonResponse({"marked":count,"unread":0})
    return redirect("notifications:list")


@require_http_methods(["POST"])
def read_one(request,public_id):
    if not request.user.is_authenticated: return JsonResponse({"detail":"Authentication required."},status=401)
    mark_read(request.user,public_ids=[public_id])
    note=Notification.objects.filter(public_id=public_id,recipient=request.user).first()
    if wants_json(request): return JsonResponse({"ok":True,"unread":unread_count(request.user)})
    return redirect(note.target_url if note and note.target_url else "notifications:list")