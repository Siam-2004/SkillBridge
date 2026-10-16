import time
from datetime import timedelta
from selenium.webdriver.common.by import By
from django.utils import timezone
from django.contrib.auth import get_user_model
from Sprint_4.selenium.base import BaseSprint4SeleniumTestCase
from apps.projects.models import Project, Team, TeamInvitation
from apps.projects import services

User = get_user_model()

class US31SeleniumInvitationExpiryTest(BaseSprint4SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.owner = User.objects.create_user(
            username='se_team_owner',
            email='se_owner@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.invitee = User.objects.create_user(
            username='se_team_invitee',
            email='se_invitee@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.client = User.objects.create_user(
            username='se_client_project',
            email='se_client@test.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )
        self.project = Project.objects.create(
            client=self.client,
            freelancer=self.owner,
            title='Selenium Expiration Workspace',
            final_price=1200,
            deadline=timezone.now() + timedelta(days=7)
        )
        self.team = Team.objects.create(
            project=self.project,
            name='Selenium Team',
            owner=self.owner
        )

    def test_browser_invitation_response_workflow(self):
        """US-31: Invitee accepts invitation within valid timeframe in browser."""
        inv = services.invite_to_team(self.team, self.invitee, self.owner)
        self.login_user('se_invitee@test.com', self.password)
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)

        # Invitee sees invitation banner
        page_source = self.driver.page_source
        self.assertIn('You are invited to join', page_source)

        # Click accept invitation
        accept_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[name="action"][value="accept"]')
        accept_btn.click()
        time.sleep(1.5)

        inv.refresh_from_db()
        self.assertEqual(inv.status, TeamInvitation.Status.ACCEPTED)
        self.assertTrue(self.team.members.filter(user=self.invitee).exists())
