import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as ts
from apps.tasks.models import Subtask
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US14SeleniumSubtaskStatusTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(email='l14@ex.com', username='lead_us14', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c14@ex.com', username='client_us14', password='p', role=Role.CLIENT, is_email_verified=True)
        self.member = User.objects.create_user(email='m14@ex.com', username='member_us14', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.project = Project.objects.create(client=c, freelancer=self.owner, title='Workflow System', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.project, name='Status Squad', owner=self.owner)
        TeamMember.objects.create(team=t, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.member, role=TeamMember.Role.MEMBER)
        self.task = ts.create_task(self.project, 'Core Engine', 'core', self.owner)
        self.subtask = ts.create_subtask(self.task, 'Unit testing pipeline', 'test', self.owner, self.member)

    def test_member_updates_subtask_status_in_browser(self):
        self.login_user('member_us14', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        select_el = self.driver.find_element(By.CSS_SELECTOR, f'form[action*="{self.subtask.id}/status/"] select[name="status"]')
        Select(select_el).select_by_value('COMPLETED')
        time.sleep(1.5)
        self.subtask.refresh_from_db()
        self.assertEqual(self.subtask.status, Subtask.Status.COMPLETED)