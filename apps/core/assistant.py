"""
Database-grounded AI Assistant Service for SkillBridge (Sprint 5: US-29).

Provides contextual, strictly authorized responses based solely on
projects, tasks, and team data accessible to the authenticated user.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List, Optional
from django.db.models import Q
from django.utils import timezone
from apps.projects.models import Project, Review, Dispute, TeamMember
from apps.tasks.models import Task


def get_user_accessible_projects(user):
    """Return queryset of projects accessible to the user."""
    if not (user and user.is_authenticated):
        return Project.objects.none()
    if getattr(user, 'is_platform_admin', False) or user.is_superuser:
        return Project.objects.all().order_by('-created_at')
    return Project.objects.filter(
        Q(client=user) | Q(freelancer=user) | Q(team__members__user=user)
    ).distinct().order_by('-created_at')


def get_user_accessible_tasks(user):
    """Return queryset of tasks accessible to the user."""
    if not (user and user.is_authenticated):
        return Task.objects.none()
    projects = get_user_accessible_projects(user)
    return Task.objects.filter(
        Q(project__in=projects) | Q(assigned_to=user) | Q(created_by=user)
    ).distinct().select_related('project', 'assigned_to', 'created_by').order_by('deadline', 'created_at')


def process_assistant_query(user, query_text: str) -> Dict[str, Any]:
    """
    Main entry point for database-grounded AI Assistant.
    Parses user query and answers strictly using user's accessible data.
    """
    if not (user and user.is_authenticated):
        return {
            'text': "You must be logged in to use the SkillBridge AI Assistant.",
            'grounded_items': [],
            'scope': 'auth_required',
            'suggestions': ["Log in to access your projects", "Learn how SkillBridge works"]
        }

    q = (query_text or "").strip().lower()
    if not q:
        return {
            'text': "Hello! I am your SkillBridge AI Assistant. You can ask me about your active projects, assigned tasks, upcoming deadlines, team members, and SkillCoin allocations.",
            'grounded_items': [],
            'scope': 'greeting',
            'suggestions': [
                "What projects am I currently working on?",
                "What tasks are assigned to me?",
                "Which tasks have upcoming deadlines?",
                "Show my high priority tasks"
            ]
        }

    projects_qs = get_user_accessible_projects(user)
    tasks_qs = get_user_accessible_tasks(user)
    now = timezone.now()

    # 1. Check for specific project title mention in query
    mentioned_project = None
    for p in projects_qs:
        if p.title.lower() in q or (len(p.title) > 4 and p.title.lower()[:10] in q):
            mentioned_project = p
            break

    # 2. Project List / Project Status Queries
    is_project_query = any(k in q for k in ['project', 'projects', 'job', 'contract'])
    is_task_query = any(k in q for k in ['task', 'tasks', 'todo', 'to do', 'deadline', 'due', 'assignment', 'assigned', 'subtask'])
    is_team_query = any(k in q for k in ['team', 'member', 'members', 'collaborator'])
    is_dispute_query = any(k in q for k in ['dispute', 'disputes', 'issue', 'complaint', 'problem'])
    is_review_query = any(k in q for k in ['review', 'reviews', 'rating', 'feedback', 'stars'])
    is_money_query = any(k in q for k in ['money', 'budget', 'price', 'skillcoin', 'allocation', 'pay', 'paid'])
    is_summary_query = any(k in q for k in ['summary', 'overview', 'dashboard', 'status', 'everything', 'update'])

    # Specific Project Inquiry
    if mentioned_project and not is_task_query:
        p = mentioned_project
        p_tasks = tasks_qs.filter(project=p)
        total_tasks = p_tasks.count()
        completed_tasks = p_tasks.filter(status=Task.Status.COMPLETED).count()
        members = TeamMember.objects.filter(team__project=p).select_related('user')
        
        reply = [
            f"### Project Details: **{p.title}**",
            f"- **Status:** `{p.get_status_display()}`",
            f"- **Client:** {p.client.get_full_name() or p.client.email}",
            f"- **Freelancer / Lead:** {p.freelancer.get_full_name() or p.freelancer.email}",
            f"- **Total Budget:** {p.final_price} SkillCoins",
            f"- **Deadline:** {p.deadline.strftime('%B %d, %Y') if p.deadline else 'Not set'}",
            f"- **Task Progress:** {completed_tasks}/{total_tasks} completed",
        ]
        if members.exists():
            team_names = ", ".join([m.user.get_full_name() or m.user.email for m in members])
            reply.append(f"- **Team Members:** {team_names}")

        return {
            'text': "\n".join(reply),
            'grounded_items': [{'type': 'project', 'id': str(p.public_id), 'title': p.title, 'status': p.status, 'url': p.get_absolute_url()}],
            'scope': 'project_detail',
            'suggestions': [
                f"What tasks are in {p.title}?",
                "What tasks are assigned to me?",
                "Show my high priority tasks"
            ]
        }

    # Dispute queries
    if is_dispute_query:
        disputes = Dispute.objects.filter(project__in=projects_qs).select_related('project', 'raised_by')
        if not disputes.exists():
            return {
                'text': "There are currently **no disputes** logged on any of your accessible projects. All projects are operating smoothly without open disputes.",
                'grounded_items': [],
                'scope': 'dispute',
                'suggestions': ["Show my active projects", "What tasks are assigned to me?"]
            }
        items = []
        lines = [f"Found **{disputes.count()} dispute(s)** across your projects:\n"]
        for d in disputes:
            lines.append(f"- **{d.project.title}**: Dispute status `{d.get_status_display()}`. Reason: *{d.get_reason_display()}*. Raised by {d.raised_by.get_full_name() or d.raised_by.email}.")
            if d.admin_resolution:
                lines.append(f"  *Resolution:* {d.admin_resolution}")
            items.append({'type': 'dispute', 'id': str(d.public_id), 'title': f"Dispute on {d.project.title}", 'status': d.status})
        return {
            'text': "\n".join(lines),
            'grounded_items': items,
            'scope': 'dispute',
            'suggestions': ["Show my active projects", "What tasks are assigned to me?"]
        }

    # Review queries
    if is_review_query:
        reviews = Review.objects.filter(project__in=projects_qs).select_related('project', 'reviewer', 'reviewee')
        if not reviews.exists():
            return {
                'text': "There are no reviews submitted yet on your accessible projects. Reviews can be submitted once a project is marked as Completed.",
                'grounded_items': [],
                'scope': 'review',
                'suggestions': ["Show my active projects", "List completed projects"]
            }
        lines = [f"Found **{reviews.count()} review(s)** on your projects:\n"]
        for r in reviews:
            stars = "★" * r.rating + "☆" * (5 - r.rating)
            lines.append(f"- **{r.project.title}** ({stars} {r.rating}/5): \"{r.feedback}\" — by {r.reviewer.get_full_name() or r.reviewer.email} for {r.reviewee.get_full_name() or r.reviewee.email}")
        return {
            'text': "\n".join(lines),
            'grounded_items': [],
            'scope': 'review',
            'suggestions': ["Show my active projects", "What tasks are assigned to me?"]
        }

    # Team queries
    if is_team_query:
        projects_with_team = projects_qs.filter(team__isnull=False)
        if not projects_with_team.exists():
            return {
                'text': "None of your current projects have a dedicated multi-member team established.",
                'grounded_items': [],
                'scope': 'team',
                'suggestions': ["What projects am I currently working on?", "What tasks are assigned to me?"]
            }
        lines = ["### Your Project Teams:\n"]
        items = []
        for p in projects_with_team:
            members = TeamMember.objects.filter(team=p.team).select_related('user')
            m_list = [f"{m.user.get_full_name() or m.user.email} ({m.get_role_display()})" for m in members]
            lines.append(f"- **{p.title}** (Team: *{p.team.name}*):")
            lines.append(f"  Members: {', '.join(m_list) if m_list else 'No members joined yet'}")
            items.append({'type': 'project', 'id': str(p.public_id), 'title': p.title, 'status': p.status, 'url': p.get_absolute_url()})
        return {
            'text': "\n".join(lines),
            'grounded_items': items,
            'scope': 'team',
            'suggestions': ["What tasks are assigned to me?", "Show my high priority tasks"]
        }

    # Task Queries
    if is_task_query:
        scoped_tasks = tasks_qs
        title_prefix = "Tasks"

        # Check filter by project
        if mentioned_project:
            scoped_tasks = scoped_tasks.filter(project=mentioned_project)
            title_prefix = f"Tasks for **{mentioned_project.title}**"

        # Filter by assignment to me
        if 'assigned to me' in q or 'my task' in q or 'my tasks' in q or 'assigned' in q:
            scoped_tasks = scoped_tasks.filter(assigned_to=user)
            title_prefix = "Tasks Assigned to You"

        # Filter by status
        if 'todo' in q or 'to do' in q:
            scoped_tasks = scoped_tasks.filter(status=Task.Status.TODO)
            title_prefix += " (To Do)"
        elif 'in progress' in q or 'progress' in q:
            scoped_tasks = scoped_tasks.filter(status=Task.Status.IN_PROGRESS)
            title_prefix += " (In Progress)"
        elif 'review' in q:
            scoped_tasks = scoped_tasks.filter(status=Task.Status.IN_REVIEW)
            title_prefix += " (In Review)"
        elif 'completed' in q or 'done' in q:
            scoped_tasks = scoped_tasks.filter(status=Task.Status.COMPLETED)
            title_prefix += " (Completed)"

        # Filter by priority
        if 'high priority' in q or 'urgent' in q or 'high' in q:
            scoped_tasks = scoped_tasks.filter(priority=Task.Priority.HIGH)
            title_prefix += " [High Priority]"

        # Filter by upcoming deadline
        if 'deadline' in q or 'due' in q:
            scoped_tasks = scoped_tasks.filter(status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS], deadline__isnull=False).order_by('deadline')
            title_prefix = "Upcoming Task Deadlines"

        count = scoped_tasks.count()
        if count == 0:
            return {
                'text': f"No matching tasks found for your query under: **{title_prefix}**.",
                'grounded_items': [],
                'scope': 'tasks',
                'suggestions': ["What projects am I currently working on?", "Show all my tasks", "Upcoming deadlines"]
            }

        lines = [f"### {title_prefix} ({count} found):\n"]
        items = []
        for t in scoped_tasks[:15]:
            due_str = t.deadline.strftime('%b %d, %Y') if t.deadline else "No deadline"
            assignee = t.assigned_to.get_full_name() if t.assigned_to else "Unassigned"
            alloc_str = f" | {t.skillcoin_allocation} SC" if t.skillcoin_allocation else ""
            lines.append(f"- **{t.title}** [`{t.get_status_display()}` | Priority: `{t.get_priority_display()}`]")
            lines.append(f"  *Project:* {t.project.title} | *Assigned to:* {assignee} | *Due:* {due_str}{alloc_str}")
            items.append({
                'type': 'task',
                'id': str(t.public_id),
                'title': t.title,
                'status': t.status,
                'priority': t.priority,
                'project_title': t.project.title,
                'deadline': due_str
            })

        return {
            'text': "\n".join(lines),
            'grounded_items': items,
            'scope': 'tasks',
            'suggestions': [
                "Show my high priority tasks",
                "Which tasks have upcoming deadlines?",
                "What projects am I currently working on?"
            ]
        }

    # Projects Query
    if is_project_query:
        scoped_projects = projects_qs
        title_prefix = "Your Accessible Projects"

        if 'active' in q or 'in progress' in q:
            scoped_projects = scoped_projects.filter(status__in=[Project.Status.ACTIVE, Project.Status.IN_PROGRESS])
            title_prefix = "Your Active Projects"
        elif 'completed' in q:
            scoped_projects = scoped_projects.filter(status=Project.Status.COMPLETED)
            title_prefix = "Your Completed Projects"

        count = scoped_projects.count()
        if count == 0:
            return {
                'text': f"No projects found matching `{title_prefix}`.",
                'grounded_items': [],
                'scope': 'projects',
                'suggestions': ["What tasks are assigned to me?", "Help"]
            }

        lines = [f"### {title_prefix} ({count} total):\n"]
        items = []
        for p in scoped_projects[:10]:
            role = "Client" if p.client_id == user.pk else ("Freelancer" if p.freelancer_id == user.pk else "Team Member")
            due_str = p.deadline.strftime('%b %d, %Y') if p.deadline else "No deadline"
            lines.append(f"- **{p.title}** [`{p.get_status_display()}`]")
            lines.append(f"  *Your role:* {role} | *Budget:* {p.final_price} SC | *Deadline:* {due_str}")
            items.append({
                'type': 'project',
                'id': str(p.public_id),
                'title': p.title,
                'status': p.status,
                'url': p.get_absolute_url()
            })

        return {
            'text': "\n".join(lines),
            'grounded_items': items,
            'scope': 'projects',
            'suggestions': [
                "What tasks are assigned to me?",
                "Which tasks have upcoming deadlines?",
                "Show my high priority tasks"
            ]
        }

    # Summary / Overview Query
    if is_summary_query:
        active_projects_count = projects_qs.filter(status__in=[Project.Status.ACTIVE, Project.Status.IN_PROGRESS]).count()
        completed_projects_count = projects_qs.filter(status=Project.Status.COMPLETED).count()
        my_tasks = tasks_qs.filter(assigned_to=user)
        pending_my_tasks = my_tasks.filter(status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]).count()
        urgent_tasks = my_tasks.filter(priority=Task.Priority.HIGH, status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]).count()

        lines = [
            "### Overview & Work Summary",
            f"- **Active Projects:** {active_projects_count}",
            f"- **Completed Projects:** {completed_projects_count}",
            f"- **Pending Tasks Assigned to You:** {pending_my_tasks}",
            f"- **High-Priority Pending Tasks:** {urgent_tasks}",
        ]
        return {
            'text': "\n".join(lines),
            'grounded_items': [],
            'scope': 'summary',
            'suggestions': [
                "What tasks are assigned to me?",
                "What projects am I currently working on?",
                "Which tasks have upcoming deadlines?"
            ]
        }

    # Off-topic / Non-grounded Query Guardrail
    return {
        'text': (
            "I am SkillBridge's Project & Task AI Assistant. I am strictly grounded to answer questions "
            "about projects, tasks, deadlines, team allocations, and disputes that you are authorized to access.\n\n"
            "Here are some examples of questions you can ask me:\n"
            "- *\"What projects am I currently working on?\"*\n"
            "- *\"List all tasks assigned to me\"*\n"
            "- *\"What tasks have upcoming deadlines?\"*\n"
            "- *\"Show my high priority tasks\"*\n"
            "- *\"What is the status of [Project Name]?\"*"
        ),
        'grounded_items': [],
        'scope': 'guardrail',
        'suggestions': [
            "What projects am I currently working on?",
            "What tasks are assigned to me?",
            "Which tasks have upcoming deadlines?"
        ]
    }
