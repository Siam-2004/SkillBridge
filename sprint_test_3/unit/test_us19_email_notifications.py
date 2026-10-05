from decimal import Decimal
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as ts
from apps.projects import services as ps
from apps.notifications import triggers

class US19EmailNotificationsTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='c@ex.com', username='client', password='p', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='l@ex.com', username='lead', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='d@ex.com', username='dev', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        self.t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=self.t, user=self.own, role=TeamMember.Role.OWNER)

    def test_email_triggers(self):
        inv = ps.invite_to_team(self.t, self.mem, self.own)
        triggers.trigger_team_invitation_email(inv)
        self.assertIn(self.mem.email, mail.outbox[-1].to)

        task = ts.create_task(self.p, 'T', '', self.own)
        st = ts.create_subtask(task, 'S', '', self.own, self.mem)
        triggers.trigger_task_assigned_email(st, self.own)
        self.assertIn(self.mem.email, mail.outbox[-1].to)

        triggers.trigger_deadline_reminder_email(self.p, self.own)
        self.assertIn(self.own.email, mail.outbox[-1].to)