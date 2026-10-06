from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.projects.models import Project, Team, TeamMember
from apps.tasks.models import Task, Subtask
from apps.tasks import services as ts

class US14SubtaskStatusWorkflowTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='siam1@gmail.com', username='client', password='siam', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='siam2@gmail.com', username='own', password='siam', role=Role.FREELANCER, is_email_verified=True)
        self.ma = User.objects.create_user(email='siam3@gmail.com', username='dev_a', password='siam', role=Role.FREELANCER, is_email_verified=True)
        self.mb = User.objects.create_user(email='siam4@gmail.com', username='dev_b', password='siam', role=Role.FREELANCER, is_email_verified=True)
        p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=p, name='T', owner=self.own)
        for u in [self.own, self.ma, self.mb]: TeamMember.objects.create(team=t, user=u, role=TeamMember.Role.OWNER if u==self.own else TeamMember.Role.MEMBER)
        self.task = ts.create_task(p, 'T', '', self.own)
        self.st = ts.create_subtask(self.task, 'S', '', self.own, self.ma)

    def test_status_workflow(self):
        for s in [Subtask.Status.IN_PROGRESS, Subtask.Status.IN_REVIEW, Subtask.Status.COMPLETED]:
            ts.update_subtask_status(self.st, s, self.ma)
            self.st.refresh_from_db()
            self.assertEqual(self.st.status, s)

    def test_unassigned_denied_and_invalid_state(self):
        with self.assertRaises(PermissionDenied): ts.update_subtask_status(self.st, Subtask.Status.IN_PROGRESS, self.mb)
        with self.assertRaises(ValidationFailed): ts.update_subtask_status(self.st, 'INVALID', self.ma)

    def test_parent_task_auto_completed(self):
        ts.update_subtask_status(self.st, Subtask.Status.COMPLETED, self.ma)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)
