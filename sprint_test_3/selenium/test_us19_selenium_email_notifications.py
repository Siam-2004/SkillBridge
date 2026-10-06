import time
from decimal import Decimal
from django.core import mail
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US19SeleniumEmailNotificationsTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(email='l19_sel@ex.com', username='lead_us19', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c19_sel@ex.com', username='client_us19', password='p', role=Role.CLIENT, is_email_verified=True)
        self.invitee = User.objects.create_user(email='inv_sel@ex.com', username='inv_us19', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.project = Project.objects.create(client=c, freelancer=self.owner, title='Notification Selenium Project', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        self.team = Team.objects.create(project=self.project, name='Email Ops Squad', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)

    def test_invite_member_in_browser_triggers_email_notification(self):
        self.login_user('lead_us19', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        invite_form = self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/team/invite/"]')
        invite_form.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(1.5)
        self.assertIn('Invited', self.driver.page_source)
        self.assertTrue(any('inv_sel@ex.com' in m.to or 'Team Invitation' in m.subject for m in mail.outbox))
