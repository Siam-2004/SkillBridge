from __future__ import annotations
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from apps.core.permissions import verified_required
from apps.core.exceptions import DomainError
from apps.accounts.models import User
from apps.projects.models import Project
from apps.tasks.models import Task, Subtask, TaskFile
from apps.tasks import services

@verified_required
@require_POST
def task_create(request, project_public_id):
    p = get_object_or_404(Project, public_id=project_public_id)
    uid = request.POST.get('assigned_to')
    try:
        t = services.create_task(p, request.POST.get('title','').strip(), request.POST.get('description','').strip(), request.user, User.objects.filter(pk=uid).first() if uid else None, request.POST.get('priority','MEDIUM'))
        messages.success(request, f'Task "{t.title}" created.')
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=p.public_id)

@verified_required
@require_POST
def task_status_update(request, task_id):
    t = get_object_or_404(Task.objects.select_related('project'), pk=task_id)
    try:
        services.update_task_status(t, request.POST.get('status'), request.user)
        messages.success(request, 'Task status updated.')
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=t.project.public_id)

@verified_required
@require_POST
def subtask_create(request, task_id):
    t = get_object_or_404(Task.objects.select_related('project'), pk=task_id)
    uid = request.POST.get('assigned_to')
    try:
        st = services.create_subtask(t, request.POST.get('title','').strip(), request.POST.get('description','').strip(), request.user, User.objects.filter(pk=uid).first() if uid else None)
        messages.success(request, f'Subtask "{st.title}" added.')
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=t.project.public_id)

@verified_required
@require_POST
def subtask_assign(request, subtask_id):
    st = get_object_or_404(Subtask.objects.select_related('task__project'), pk=subtask_id)
    try:
        services.assign_subtask(st, get_object_or_404(User, pk=request.POST.get('assigned_to')), request.user)
        messages.success(request, f'Assigned "{st.title}".')
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=st.task.project.public_id)

@verified_required
@require_POST
def subtask_status_update(request, subtask_id):
    st = get_object_or_404(Subtask.objects.select_related('task__project'), pk=subtask_id)
    try:
        services.update_subtask_status(st, request.POST.get('status'), request.user)
        messages.success(request, 'Status updated.')
    except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=st.task.project.public_id)

@verified_required
@require_POST
def task_file_upload(request, task_id):
    t = get_object_or_404(Task.objects.select_related('project'), pk=task_id)
    if 'file' in request.FILES:
        try:
            services.upload_task_file(t, request.user, request.FILES['file'])
            messages.success(request, 'File uploaded.')
        except DomainError as e: messages.error(request, e.message)
    return redirect('projects:detail', public_id=t.project.public_id)

@verified_required
def task_file_download(request, task_id, file_id):
    t = get_object_or_404(Task.objects.select_related('project'), pk=task_id)
    if not t.project.has_access(request.user): return HttpResponseForbidden("Access Denied")
    tf = get_object_or_404(TaskFile, pk=file_id, task=t)
    try: return FileResponse(tf.file.open('rb'), as_attachment=True, filename=tf.original_name)
    except Exception: raise Http404("Not found")
