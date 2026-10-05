from django.conf import settings
from django.core.mail import send_mail

def trigger_team_invitation_email(inv):
    send_mail(f"[SkillBridge] Team Invitation: {inv.team.name}",
              f"Hi {inv.invitee.username},\n{inv.invited_by.username} invited you to '{inv.team.name}' on project '{inv.team.project.title}'.",
              settings.DEFAULT_FROM_EMAIL, [inv.invitee.email], fail_silently=True)

def trigger_task_assigned_email(item, assigned_by):
    if item.assigned_to and item.assigned_to.email:
        send_mail(f"[SkillBridge] Task Assigned: {item.title}",
                  f"Hi {item.assigned_to.username},\nYou were assigned '{item.title}' by {assigned_by.username}.",
                  settings.DEFAULT_FROM_EMAIL, [item.assigned_to.email], fail_silently=True)

def trigger_subtask_status_email(subtask, actor, old_st, new_st, rec):
    if rec and rec.email:
        send_mail(f"[SkillBridge] Subtask {subtask.title} is now {new_st}",
                  f"Hi {rec.username},\n{actor.username} changed status from {old_st} to {new_st}.",
                  settings.DEFAULT_FROM_EMAIL, [rec.email], fail_silently=True)

def trigger_mention_email(author, mentioned, title, text):
    if mentioned and mentioned.email:
        send_mail(f"[SkillBridge] {author.username} mentioned you in {title}",
                  f"Hi {mentioned.username},\n{author.username} wrote: {text}",
                  settings.DEFAULT_FROM_EMAIL, [mentioned.email], fail_silently=True)

def trigger_deadline_reminder_email(proj, rec):
    if rec and rec.email:
        send_mail(f"[SkillBridge] Deadline Reminder: {proj.title}",
                  f"Hi {rec.username},\nDeadline for '{proj.title}' is approaching on {proj.deadline}.",
                  settings.DEFAULT_FROM_EMAIL, [rec.email], fail_silently=True)