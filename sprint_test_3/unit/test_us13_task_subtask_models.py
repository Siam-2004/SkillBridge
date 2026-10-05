from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks.models import Task, Subtask
from apps.tasks import services as ts

class US13TaskSubtaskModelsTestCase(TestCase):
    def setUp(self):
        self.c = User.objects.create_user(email='c@ex.com', username='client', password='p', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='o@ex.com', username='own', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='m@ex.com', username='mem', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=self.c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=t, user=self.own, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.mem, role=TeamMember.Role.MEMBER)

    def test_task_and_subtask_creation(self):
        t = ts.create_task(self.p, 'Auth', 'Desc', self.own, self.own, 'HIGH')
        self.assertEqual(t.status, Task.Status.TODO)
        st = ts.create_subtask(t, 'JWT', 'Handle JWT', self.own, self.mem)
        self.assertEqual(st.assigned_to, self.mem)
        self.assertEqual(st.status, Subtask.Status.TODO)
        ts.assign_subtask(st, self.own, self.own)
        st.refresh_from_db()
        self.assertEqual(st.assigned_to, self.own)