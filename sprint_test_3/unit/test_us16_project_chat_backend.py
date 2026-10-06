from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember

class US16ProjectChatBackendTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='rifat1@gmail.com', username='client', password='p', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='rifat2@gmail.com', username='own', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='rifat3@gmail.com', username='mem', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.out = User.objects.create_user(email='rifat4@gmail.com', username='out', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=t, user=self.own, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.mem, role=TeamMember.Role.MEMBER)
        self.cli = Client()

    def test_chat_send_and_poll(self):
        self.cli.force_login(self.own)
        r = self.cli.post(f'/projects/{self.p.public_id}/chat/send/', {'content': 'Hello!'})
        self.assertEqual(r.status_code, 200)
        self.cli.force_login(self.mem)
        poll = self.cli.get(f'/projects/{self.p.public_id}/chat/poll/?after_id=0').json()
        self.assertEqual(len(poll['messages']), 1)
        self.assertEqual(poll['messages'][0]['content'], 'Hello!')

    def test_unauthorized_chat_denied(self):
        self.cli.force_login(self.out)
        self.assertEqual(self.cli.get(f'/projects/{self.p.public_id}/chat/poll/?after_id=0').status_code, 403)
