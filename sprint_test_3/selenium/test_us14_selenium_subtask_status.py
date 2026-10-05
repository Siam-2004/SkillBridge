import time

from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as task_services
from apps.tasks.models import Subtask
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US14SeleniumSubtaskStatusTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            email='lead_us14@example.com', username='lead_us14', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.client_user = User.objects.create_user(
            email='client_us14@example.com', username='client_us14', password='password123',
            role=Role.CLIENT, is_email_verified=True
        )
        self.member = User.objects.create_user(
            email='member_us14@example.com', username='member_us14', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.project = Project.objects.create(
            client=self.client_user, freelancer=self.owner, title='Workflow System',
            final_price=Decimal('1500.00'), deadline=timezone.now() + timezone.timedelta(days=10),
            status=Project.Status.ACTIVE
        )
        self.team = Team.objects.create(project=self.project, name='Status Squad', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=self.team, user=self.member, role=TeamMember.Role.MEMBER)

        self.task = task_services.create_task(project=self.project, title='Core Engine', created_by=self.owner)
        self.subtask = task_services.create_subtask(
            task=self.task, title='Unit testing pipeline', creator=self.owner, assigned_to=self.member
        )

    def test_member_updates_subtask_status_in_browser(self):
        self.login_user('member_us14@example.com', 'password123')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)

        # Locate status select dropdown for subtask
        select_el = self.driver.find_element(By.CSS_SELECTOR, f'form[action*="{self.subtask.id}/status/"] select[name="status"]')
        status_dropdown = Select(select_el)
        status_dropdown.select_by_value('COMPLETED')
        time.sleep(1.5)

        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.status, Subtask.Status.COMPLETED)