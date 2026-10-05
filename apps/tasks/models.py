from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import ZERO, MoneyField

class Task(BaseModel):
    class Status(models.TextChoices):
        TODO = ('TODO', 'To do'); IN_PROGRESS = ('IN_PROGRESS', 'In progress')
        IN_REVIEW = ('IN_REVIEW', 'In review'); COMPLETED = ('COMPLETED', 'Completed'); CANCELLED = ('CANCELLED', 'Cancelled')
    class Priority(models.TextChoices): LOW = ('LOW', 'Low'); MEDIUM = ('MEDIUM', 'Medium'); HIGH = ('HIGH', 'High')

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_tasks')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    skillcoin_allocation = MoneyField(default=ZERO)
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ('created_at',)

class Subtask(BaseModel):
    class Status(models.TextChoices):
        TODO = ('TODO', 'To do'); IN_PROGRESS = ('IN_PROGRESS', 'In progress')
        IN_REVIEW = ('IN_REVIEW', 'In review'); COMPLETED = ('COMPLETED', 'Completed')

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_subtasks')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO, db_index=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ('created_at',)

class TaskActivity(TimeStampedModel):
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='task_activities')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='activities')
    subtask = models.ForeignKey(Subtask, on_delete=models.CASCADE, null=True, blank=True, related_name='activities')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_actions')
    action = models.CharField(max_length=50)
    details = models.CharField(max_length=400)
    class Meta: ordering = ('-created_at',)

class TaskFile(BaseModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='files')
    subtask = models.ForeignKey(Subtask, on_delete=models.CASCADE, null=True, blank=True, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploaded_task_files')
    file = models.FileField(upload_to='tasks/files/%Y/%m/')
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    class Meta: ordering = ('-created_at',)

class TaskComment(BaseModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_comments')
    content = models.TextField()
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='mentioned_in_task_comments')
