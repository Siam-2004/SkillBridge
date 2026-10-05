from __future__ import annotations
import re
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.accounts.models import User
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
from apps.tasks.models import Task, Subtask, TaskActivity, TaskFile, TaskComment

def log_task_activity(project, actor, action: str, details: str, task=None, subtask=None) -> TaskActivity:
    act = TaskActivity.objects.create(project=project, task=task, subtask=subtask, actor=actor, action=action, details=details[:400])
    record_activity(ActivityVerb.TASK_ASSIGNED if action == 'ASSIGNED' else ActivityVerb.TASK_APPROVED if action == 'STATUS_CHANGED' and getattr(subtask, 'status', '') == 'COMPLETED' else ActivityVerb.TASK_STARTED,
                    description=details, actor=actor, project=project, target=subtask or task)
    return act

@transaction.atomic
def create_task(project, title: str, description: str = '', created_by: User = None, assigned_to: User | None = None, priority='MEDIUM', skillcoin_allocation=0, deadline=None) -> Task:
    if created_by and not project.has_access(created_by): raise PermissionDenied("Access denied.")
    if not title.strip(): raise ValidationFailed("Title cannot be empty.")
    t = Task.objects.create(project=project, title=title.strip(), description=description.strip(), created_by=created_by, assigned_to=assigned_to, skillcoin_allocation=skillcoin_allocation, deadline=deadline, priority=priority, status=Task.Status.TODO)
    if created_by: log_task_activity(project=project, task=t, actor=created_by, action='CREATED', details=f'Created task "{t.title}"')
    if assigned_to and created_by:
        notify(assigned_to, NotificationType.TASK_ASSIGNED, f'Task assigned: {t.title}', message=f'{created_by.username} assigned you to "{t.title}".', actor=created_by, target_url=project.get_absolute_url(), email=True)
    return t

@transaction.atomic
def create_subtask(task: Task, title: str, description: str = '', creator: User = None, assigned_to: User | None = None, due_date=None) -> Subtask:
    if creator and not task.project.has_access(creator): raise PermissionDenied("Access denied.")
    if not title.strip(): raise ValidationFailed("Title cannot be empty.")
    st = Subtask.objects.create(task=task, title=title.strip(), description=description.strip(), assigned_to=assigned_to, due_date=due_date, status=Subtask.Status.TODO)
    if creator: log_task_activity(project=task.project, task=task, subtask=st, actor=creator, action='SUBTASK_CREATED', details=f'Created subtask "{st.title}"')
    if assigned_to and creator:
        notify(assigned_to, NotificationType.TASK_ASSIGNED, f'Subtask assigned: {st.title}', message=f'{creator.username} assigned you to "{st.title}".', actor=creator, target_url=task.project.get_absolute_url(), email=True)
    return st

@transaction.atomic
def assign_subtask(subtask: Subtask, assigned_to: User, assigned_by: User) -> Subtask:
    p = subtask.task.project
    if not p.is_owner(assigned_by) and subtask.task.created_by_id != assigned_by.pk and not assigned_by.is_superuser: raise PermissionDenied("Unauthorized.")
    subtask.assigned_to = assigned_to
    subtask.save(update_fields=['assigned_to', 'updated_at'])
    log_task_activity(project=p, task=subtask.task, subtask=subtask, actor=assigned_by, action='ASSIGNED', details=f'Assigned "{subtask.title}" to {assigned_to.username}')
    notify(assigned_to, NotificationType.TASK_ASSIGNED, f'Subtask assigned: {subtask.title}', actor=assigned_by, target_url=p.get_absolute_url(), email=True)
    return subtask

@transaction.atomic
def update_subtask_status(subtask: Subtask, new_status: str, actor: User) -> Subtask:
    p = subtask.task.project
    is_lead = p.is_owner(actor) or (hasattr(p, 'team') and p.team.owner_id == actor.pk)
    if not (subtask.assigned_to_id == actor.pk or is_lead or actor.is_superuser): raise PermissionDenied("Unauthorized.")
    if new_status not in Subtask.Status.values: raise ValidationFailed(f"Invalid status '{new_status}'")
    if subtask.status == new_status: return subtask
    subtask.status = new_status
    subtask.completed_at = timezone.now() if new_status == Subtask.Status.COMPLETED else None
    subtask.save(update_fields=['status', 'completed_at', 'updated_at'])
    log_task_activity(project=p, task=subtask.task, subtask=subtask, actor=actor, action='STATUS_CHANGED', details=f'Updated "{subtask.title}" to {new_status}')
    t = subtask.task
    if new_status == Subtask.Status.COMPLETED:
        if not t.subtasks.exclude(status=Subtask.Status.COMPLETED).exists():
            t.status = Task.Status.COMPLETED
            t.save(update_fields=['status', 'updated_at'])
            log_task_activity(project=p, task=t, actor=actor, action='STATUS_CHANGED', details=f'Task "{t.title}" automatically completed')
    elif t.status == Task.Status.TODO and new_status == Subtask.Status.IN_PROGRESS:
        t.status = Task.Status.IN_PROGRESS
        t.save(update_fields=['status', 'updated_at'])
    return subtask

@transaction.atomic
def update_task_status(task: Task, new_status: str, actor: User) -> Task:
    p = task.project
    is_lead = p.is_owner(actor) or (hasattr(p, 'team') and p.team.owner_id == actor.pk)
    if not (task.assigned_to_id == actor.pk or is_lead or actor.is_superuser): raise PermissionDenied("Unauthorized.")
    if new_status not in Task.Status.values: raise ValidationFailed(f"Invalid status '{new_status}'")
    task.status = new_status
    task.completed_at = timezone.now() if new_status == Task.Status.COMPLETED else None
    task.save(update_fields=['status', 'completed_at', 'updated_at'])
    log_task_activity(project=p, task=task, actor=actor, action='STATUS_CHANGED', details=f'Marked task "{task.title}" as {new_status}')
    return task

@transaction.atomic
def upload_task_file(task: Task, uploaded_by: User, file) -> TaskFile:
    if not task.project.has_access(uploaded_by): raise PermissionDenied("Access denied.")
    tf = TaskFile.objects.create(task=task, uploaded_by=uploaded_by, file=file, original_name=getattr(file, 'name', 'file'), size_bytes=getattr(file, 'size', 0))
    log_task_activity(project=task.project, task=task, actor=uploaded_by, action='FILE_UPLOADED', details=f'Uploaded file "{tf.original_name}"')
    return tf
