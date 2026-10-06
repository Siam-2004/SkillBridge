import time
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as ts
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US13SeleniumTaskAssignmentTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(email='l13@ex.com', username='lead_us13', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c13@ex.com', username='client_us13', password='p', role=Role.CLIENT, is_email_verified=True)
        self.member = User.objects.create_user(email='m13@ex.com', username='member_us13', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.project = Project.objects.create(client=c, freelancer=self.owner, title='Task Assignment System', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.project, name='Task Squad', owner=self.owner)
        TeamMember.objects.create(team=t, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.member, role=TeamMember.Role.MEMBER)

    def test_task_creation_and_assignment_interface(self):
        self.login_user('lead_us13', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        task = ts.create_task(self.project, 'Microservices Infrastructure', 'setup', self.owner, priority='HIGH')
        ts.create_subtask(task, 'Docker compose setup', 'compose', self.owner, self.member)
        self.driver.refresh()
        time.sleep(1)
        self.assertIn('Microservices Infrastructure', self.driver.page_source)
        self.assertIn('Docker compose setup', self.driver.page_source)
        self.assertIn('member_us13', self.driver.page_source)