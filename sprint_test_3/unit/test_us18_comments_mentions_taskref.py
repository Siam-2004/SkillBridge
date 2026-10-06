from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.core.exceptions import ValidationFailed
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as ts
from apps.projects import services as ps
from apps.notifications.models import Notification, NotificationType

class US18CommentsMentionsTaskRefTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='c18@ex.com', username='client', password='p', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='a18@ex.com', username='alice', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='b18@ex.com', username='bob', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=t, user=self.own, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.mem, role=TeamMember.Role.MEMBER)

    def test_comment_mentions_and_task_reference(self):
        task = ts.create_task(self.p, 'Refactor', '', self.own)
        cmt = ps.add_project_comment(self.p, self.own, 'Hey @bob on #1', task)
        self.assertEqual(cmt.task, task)
        self.assertIn(self.mem, cmt.mentions.all())
        self.assertTrue(Notification.objects.filter(recipient=self.mem, notification_type=NotificationType.MENTION).exists())

    def test_empty_comment_rejected(self):
        with self.assertRaises(ValidationFailed): ps.add_project_comment(self.p, self.own, '   ')