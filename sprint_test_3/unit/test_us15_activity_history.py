from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks.models import Subtask, TaskActivity
from apps.tasks import services as ts

class US15ActivityHistoryTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='c15@ex.com', username='client', password='p', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='o15@ex.com', username='own', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='m15@ex.com', username='mem', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=t, user=self.own, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.mem, role=TeamMember.Role.MEMBER)

    def test_activity_logging(self):
        task = ts.create_task(self.p, 'Homepage', '', self.own)
        self.assertTrue(TaskActivity.objects.filter(project=self.p, task=task, action='CREATED').exists())
        st = ts.create_subtask(task, 'Sub', '', self.own)
        ts.assign_subtask(st, self.mem, self.own)
        self.assertTrue(TaskActivity.objects.filter(project=self.p, subtask=st, action='ASSIGNED').exists())
        ts.update_subtask_status(st, Subtask.Status.IN_PROGRESS, self.mem)
        act = TaskActivity.objects.filter(project=self.p, subtask=st, action='STATUS_CHANGED').first()
        self.assertEqual(act.actor, self.mem)

    def test_activity_details_recorded(self):
        task = ts.create_task(self.p, 'Backend', '', self.own)
        act = TaskActivity.objects.filter(project=self.p, task=task).first()
        self.assertIn('Backend', act.details)
        self.assertEqual(act.project, self.p)