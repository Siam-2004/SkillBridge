from __future__ import annotations
import re
from django.db import models, transaction
from django.utils import timezone
from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.core.models import ActivityVerb
from apps.core.services import record_activity
from apps.accounts.models import User, Role
from apps.notifications.models import NotificationType
from apps.notifications.services import notify
from apps.projects.models import Project, Team, TeamMember, TeamInvitation, ProjectFile, ProjectComment

@transaction.atomic
def create_project_from_agreement(agreement) -> Project:
    p = Project.objects.filter(agreement=agreement).first()
    if p: return p
    p = Project.objects.create(
        job=agreement.job, agreement=agreement, client=agreement.client, freelancer=agreement.freelancer,
        title=agreement.job.title, description=agreement.deliverables or agreement.job.description,
        final_price=agreement.amount, deadline=agreement.deadline, status=Project.Status.ACTIVE)
    t = Team.objects.create(project=p, name=f"{p.title[:100]} Team", owner=p.freelancer)
    TeamMember.objects.create(team=t, user=p.freelancer, role=TeamMember.Role.OWNER)
    record_activity(ActivityVerb.PROJECT_CREATED, f'Project “{p.title}” initialized', actor=p.freelancer, project=p, target=p)
    return p

@transaction.atomic
def create_team(project: Project, name: str, owner: User) -> Team:
    if not project.is_owner(owner): raise PermissionDenied("Only owner can create team.")
    if hasattr(project, 'team'): return project.team
    t = Team.objects.create(project=project, name=name.strip(), owner=owner)
    TeamMember.objects.create(team=t, user=owner, role=TeamMember.Role.OWNER)
    record_activity(ActivityVerb.TEAM_CREATED, f'Team “{t.name}” created', actor=owner, project=project, target=t)
    return t

def search_freelancers(query: str = '', exclude_team: Team | None = None):
    qs = User.objects.filter(role=Role.FREELANCER, is_active=True)
    if query:
        qs = qs.filter(models.Q(username__icontains=query) | models.Q(first_name__icontains=query) | models.Q(email__icontains=query))
    if exclude_team:
        qs = qs.exclude(id__in=exclude_team.members.values_list('user_id', flat=True))
    return qs[:20]

@transaction.atomic
def invite_to_team(team: Team, invitee: User, invited_by: User, message: str = '') -> TeamInvitation:
    if not (team.owner_id == invited_by.pk or invited_by.is_superuser or getattr(invited_by, 'is_platform_admin', False)):
        raise PermissionDenied("Only team owner can invite members.")
    if team.members.filter(user=invitee).exists():
        raise ValidationFailed(f"{invitee.username} is already a team member.")
    inv, _ = TeamInvitation.objects.get_or_create(team=team, invitee=invitee, status=TeamInvitation.Status.PENDING,
                                                  defaults={'invited_by': invited_by, 'message': message.strip()})
    notify(invitee, NotificationType.TEAM_INVITATION, f'Team Invitation: {team.name}',
           message=f'{invited_by.username} invited you to join "{team.name}".', actor=invited_by, target_url=team.project.get_absolute_url(), email=True)
    return inv

def respond_to_invitation(invitation: TeamInvitation, user: User, accept: bool) -> TeamInvitation:
    if invitation.invitee_id != user.pk and not user.is_superuser: raise PermissionDenied("Unauthorized.")
    if invitation.status != TeamInvitation.Status.PENDING: raise ValidationFailed("Already processed.")
    if invitation.is_expired:
        TeamInvitation.objects.filter(pk=invitation.pk).update(status=TeamInvitation.Status.EXPIRED, updated_at=timezone.now())
        invitation.status = TeamInvitation.Status.EXPIRED
        raise ValidationFailed("Invitation has expired (48-hour limit).")
    with transaction.atomic():
        invitation.status = TeamInvitation.Status.ACCEPTED if accept else TeamInvitation.Status.DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=['status', 'responded_at', 'updated_at'])
    if accept:
        TeamMember.objects.get_or_create(team=invitation.team, user=user, defaults={'role': TeamMember.Role.MEMBER})
        verb, notif_type = ActivityVerb.INVITATION_ACCEPTED, NotificationType.INVITATION_ACCEPTED
    else:
        verb, notif_type = ActivityVerb.INVITATION_DECLINED, NotificationType.INVITATION_DECLINED
    record_activity(verb, f'{user.username} {invitation.status.lower()} invitation', actor=user, project=invitation.team.project, target=invitation.team)
    notify(invitation.invited_by, notif_type, f'{user.username} {invitation.status.lower()} invitation', actor=user, target_url=invitation.team.project.get_absolute_url(), email=True)
    return invitation

@transaction.atomic
def add_project_comment(project: Project, author: User, content: str, task=None) -> ProjectComment:
    if not project.has_access(author): raise PermissionDenied("Access denied.")
    if not content.strip(): raise ValidationFailed("Comment cannot be empty.")
    c = ProjectComment.objects.create(project=project, task=task, author=author, content=content.strip())
    for m in User.objects.filter(username__in=set(re.findall(r'@([a-zA-Z0-9_.-]+)', content))):
        if project.has_access(m) and m.pk != author.pk:
            c.mentions.add(m)
            notify(m, NotificationType.MENTION, f'{author.username} mentioned you in {project.title}', message=content[:100], actor=author, target_url=project.get_absolute_url(), email=True)
    record_activity(ActivityVerb.MESSAGE_SENT, f'Comment by {author.username}', actor=author, project=project, target=c)
    return c

@transaction.atomic
def upload_project_file(project: Project, uploaded_by: User, file, description: str = '') -> ProjectFile:
    if not project.has_access(uploaded_by): raise PermissionDenied("Access denied.")
    pf = ProjectFile.objects.create(project=project, uploaded_by=uploaded_by, file=file, original_name=getattr(file, 'name', 'file'), size_bytes=getattr(file, 'size', 0), description=description.strip())
    record_activity(ActivityVerb.FILE_UPLOADED, f'Uploaded "{pf.original_name}"', actor=uploaded_by, project=project, target=pf)
    return pf
