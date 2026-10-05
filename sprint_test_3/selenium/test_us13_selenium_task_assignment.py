import time

from decimal import Decimal
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as task_services
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US13SeleniumTaskAssignmentTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            email='lead_us13@example.com', username='lead_us13', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.client_user = User.objects.create_user(
            email='client_us13@example.com', username='client_us13', password='password123',
            role=Role.CLIENT, is_email_verified=True
        )
        self.member = User.objects.create_user(
            email='member_us13@example.com', username='member_us13', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.project = Project.objects.create(
            client=self.client_user, freelancer=self.owner, title='Task Assignment System',
            final_price=Decimal('2000.00'), deadline=timezone.now() + timezone.timedelta(days=15),
            status=Project.Status.ACTIVE
        )
        self.team = Team.objects.create(project=self.project, name='Task Squad', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=self.team, user=self.member, role=TeamMember.Role.MEMBER)

    def test_task_creation_and_assignment_interface(self):
        self.login_user('lead_us13@example.com', 'password123')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)

        # Pre-create task and subtask
        task = task_services.create_task(
            project=self.project, title='Microservices Infrastructure', created_by=self.owner, priority='HIGH'
        )
        subtask = task_services.create_subtask(
            task=task, title='Docker compose setup', creator=self.owner, assigned_to=self.member
        )

        self.driver.refresh()
        time.sleep(1)

        # Verify task and subtask appear in DOM
        page_source = self.driver.page_source
        self.assertIn('Microservices Infrastructure', page_source)
        self.assertIn('Docker compose setup', page_source)
        self.assertIn('member_us13', page_source)