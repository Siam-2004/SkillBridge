import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.projects import services as ps
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US12SeleniumTeamInvitationTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(email='l12@ex.com', username='lead_us12', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c12@ex.com', username='client_us12', password='p', role=Role.CLIENT, is_email_verified=True)
        self.inv = User.objects.create_user(email='s12@ex.com', username='spec_us12', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.owner, title='Cloud Native Architecture', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        self.t = Team.objects.create(project=self.p, name='Cloud Guild', owner=self.owner)
        TeamMember.objects.create(team=self.t, user=self.owner, role=TeamMember.Role.OWNER)

    def test_owner_views_team_and_invites_freelancer(self):
        self.login_user('lead_us12', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.p.public_id}/')
        time.sleep(1)
        self.assertIn('Cloud Native Architecture', self.driver.page_source)
        ps.invite_to_team(self.t, self.inv, self.owner)
        self.login_user('spec_us12', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.p.public_id}/')
        time.sleep(1)
        self.assertIn('You are invited to join Cloud Guild', self.driver.page_source)
        self.assertIsNotNone(self.driver.find_element(By.CSS_SELECTOR, 'button[value="accept"]'))
