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
        self.owner = User.objects.create_user(email='l18@ex.com', username='lead_us18', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c18@ex.com', username='client_us18', password='p', role=Role.CLIENT, is_email_verified=True)
        self.member = User.objects.create_user(email='d18@ex.com', username='dev_us18', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.project = Project.objects.create(client=c, freelancer=self.owner, title='Discussion Collaboration', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.project, name='Collab Squad', owner=self.owner)
        TeamMember.objects.create(team=t, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.member, role=TeamMember.Role.MEMBER)

    def test_post_comment_with_mention_in_browser(self):
        self.login_user('lead_us18', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        comment_box = self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/comments/add/"] textarea[name="content"]')
        comment_text = "Good progress @dev_us18, please push the report."
        comment_box.send_keys(comment_text)
        self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/comments/add/"] button[type="submit"]').click()
        time.sleep(1.5)
        self.assertIn(comment_text, self.driver.page_source)
