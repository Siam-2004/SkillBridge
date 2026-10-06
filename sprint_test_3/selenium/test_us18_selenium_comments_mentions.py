import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US18SeleniumCommentsMentionsTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            email='lead_us18@example.com', username='lead_us18', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.client_user = User.objects.create_user(
            email='client_us18@example.com', username='client_us18', password='password123',
            role=Role.CLIENT, is_email_verified=True
        )
        self.member = User.objects.create_user(
            email='dev_us18@example.com', username='dev_us18', password='password123',
            role=Role.FREELANCER, is_email_verified=True
        )
        self.project = Project.objects.create(
            client=self.client_user, freelancer=self.owner, title='Discussion Collaboration',
            final_price=Decimal('1600.00'), deadline=timezone.now() + timezone.timedelta(days=8),
            status=Project.Status.ACTIVE
        )
        self.team = Team.objects.create(project=self.project, name='Collab Squad', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=self.team, user=self.member, role=TeamMember.Role.MEMBER)

    def test_post_comment_with_mention_in_browser(self):
        self.login_user('lead_us18@example.com', 'password123')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)

        comment_box = self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/comments/add/"] textarea[name="content"]')
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/comments/add/"] button[type="submit"]')

        comment_text = "Good progress @dev_us18, please push the final report."
        comment_box.send_keys(comment_text)
        submit_btn.click()
        time.sleep(1.5)

        self.assertIn(comment_text, self.driver.page_source)
