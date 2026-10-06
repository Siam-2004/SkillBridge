from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.core.permissions import verified_required
from apps.core.exceptions import DomainError
from apps.accounts.models import User
from apps.projects.models import Project, TeamInvitation, ProjectFile, ProjectComment
from apps.projects import services
from apps.tasks.models import Task

@verified_required
def project_list(request):
    u = request.user
    q = Project.objects.filter(client=u) if u.is_client else Project.objects.filter(models.Q(freelancer=u) | models.Q(team__members__user=u)).distinct()
    return render(request, 'projects/list.html', {'projects': q, 'page_title': 'Projects Workspace', 'nav': 'projects'})

@verified_required
def project_detail(request, public_id):
    p = get_object_or_404(Project.objects.select_related('client', 'freelancer', 'team'), public_id=public_id)
    if not p.has_access(request.user): raise PermissionDenied("Access denied.")
    t = getattr(p, 'team', None)
    return render(request, 'projects/detail.html', {
        'project': p, 'team': t, 'is_owner': p.is_owner(request.user), 'page_title': p.title, 'nav': 'projects',
        'team_members': t.members.select_related('user').all() if t else [],
        'pending_invites': t.invitations.filter(status=TeamInvitation.Status.PENDING).select_related('invitee') if t else [],
        'my_invite': TeamInvitation.objects.filter(team=t, invitee=request.user, status=TeamInvitation.Status.PENDING).first() if t else None,
        'tasks': p.tasks.prefetch_related('subtasks', 'subtasks__assigned_to', 'files').all(),
        'files': p.files.select_related('uploaded_by').all(),
        'comments': p.comments.select_related('author', 'task').prefetch_related('mentions').all(),
        'activities': p.task_activities.select_related('actor', 'task', 'subtask').all()[:30],
        'available_freelancers': services.search_freelancers(query=request.GET.get('q', '').strip(), exclude_team=t) if p.is_owner(request.user) and t else [],
    })

@verified_required
@require_POST
def create_team(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    try: services.create_team(p, request.POST.get('name', '').strip() or f"{p.title[:80]} Team", request.user)
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=p.public_id)

@verified_required
@require_POST
def invite_member(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    if hasattr(p, 'team'):
        try: services.invite_to_team(p.team, get_object_or_404(User, pk=request.POST.get('invitee_id')), request.user, request.POST.get('message', ''))
        except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=p.public_id)

@verified_required
@require_POST
def respond_invitation(request, invitation_id):
    inv = get_object_or_404(TeamInvitation, pk=invitation_id)
    try: services.respond_to_invitation(inv, request.user, (request.POST.get('action') == 'accept'))
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=inv.team.project.public_id)

@verified_required
@require_POST
def upload_file(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    if 'file' in request.FILES:
        try: services.upload_project_file(p, request.user, request.FILES['file'], request.POST.get('description', ''))
        except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=p.public_id)

@verified_required
def download_file(request, public_id, file_id):
    p = get_object_or_404(Project, public_id=public_id)
    if not p.has_access(request.user): return HttpResponseForbidden("Access Denied.")
    pf = get_object_or_404(ProjectFile, pk=file_id, project=p)
    return FileResponse(pf.file.open('rb'), as_attachment=True, filename=pf.original_name)

@verified_required
@require_POST
def add_comment(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    t = Task.objects.filter(pk=request.POST.get('task_id'), project=p).first() if request.POST.get('task_id') else None
    try: services.add_project_comment(p, request.user, request.POST.get('content', ''), t)
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=p.public_id)

@verified_required
def project_chat_view(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    if not p.has_access(request.user): raise PermissionDenied()
    return render(request, 'projects/chat.html', {'project': p, 'page_title': f'Chat — {p.title}', 'nav': 'projects'})

@verified_required
def project_chat_poll(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    if not p.has_access(request.user): return HttpResponseForbidden()
    msgs = [{'id': c.id, 'author': c.author.username, 'author_name': c.author.username, 'is_me': c.author_id == request.user.pk, 'content': c.content, 'task_id': c.task_id, 'task_title': c.task.title if c.task else None, 'created_at': c.created_at.strftime("%I:%M %p · %d %b")} for c in ProjectComment.objects.filter(project=p, id__gt=int(request.GET.get('after_id', 0))).select_related('author', 'task').order_by('id')]
    return JsonResponse({'messages': msgs})

@verified_required
@require_POST
def project_chat_send(request, public_id):
    p = get_object_or_404(Project, public_id=public_id)
    if not p.has_access(request.user): return HttpResponseForbidden()
    body = request.POST.get('content', '').strip()
    if not body: return JsonResponse({'error': 'Empty'}, status=400)
    t = Task.objects.filter(pk=request.POST.get('task_id'), project=p).first() if request.POST.get('task_id') else None
    c = services.add_project_comment(p, request.user, body, t)
    return JsonResponse({'status': 'ok', 'message': {'id': c.id, 'author': c.author.username, 'content': c.content, 'created_at': c.created_at.strftime("%I:%M %p")}})
