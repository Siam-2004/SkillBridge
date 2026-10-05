from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from apps.core.models import BaseModel, TimeStampedModel
from apps.core.money import MoneyField

class Project(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = ('ACTIVE', 'Active'); IN_PROGRESS = ('IN_PROGRESS', 'In progress')
        COMPLETED = ('COMPLETED', 'Completed'); CANCELLED = ('CANCELLED', 'Cancelled')

    job = models.ForeignKey('marketplace.Job', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    agreement = models.ForeignKey('agreements.Agreement', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='client_projects')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='freelancer_projects')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    final_price = MoneyField()
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def has_access(self, u):
        if not (u and u.is_authenticated): return False
        if getattr(u, 'is_platform_admin', False) or u.is_superuser or u.pk in (self.client_id, self.freelancer_id): return True
        return hasattr(self, 'team') and (self.team.members.filter(user=u).exists() or self.team.invitations.filter(invitee=u, status='PENDING').exists())

    def is_owner(self, u):
        return bool(u and u.is_authenticated and (getattr(u, 'is_platform_admin', False) or u.is_superuser or u.pk == self.freelancer_id))

    def get_absolute_url(self):
        return reverse('projects:detail', args=[self.public_id])

class Team(BaseModel):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='team')
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_teams')
    def is_member(self, u): return bool(u and u.is_authenticated and self.members.filter(user=u).exists())

class TeamMember(TimeStampedModel):
    class Role(models.TextChoices): OWNER = ('OWNER', 'Owner'); MEMBER = ('MEMBER', 'Member')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(default=timezone.now)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['team', 'user'], name='unique_team_member')]

class TeamInvitation(BaseModel):
    class Status(models.TextChoices): PENDING = ('PENDING', 'Pending'); ACCEPTED = ('ACCEPTED', 'Accepted'); DECLINED = ('DECLINED', 'Declined')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invitations')
    invitee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_team_invitations')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_team_invitations')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    message = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ('-created_at',)

class ProjectFile(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploaded_project_files')
    file = models.FileField(upload_to='projects/files/%Y/%m/')
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    description = models.CharField(max_length=300, blank=True)

class ProjectComment(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    task = models.ForeignKey('tasks.Task', on_delete=models.SET_NULL, null=True, blank=True, related_name='project_comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authored_project_comments')
    content = models.TextField()
    mentions = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='mentioned_in_project_comments')
