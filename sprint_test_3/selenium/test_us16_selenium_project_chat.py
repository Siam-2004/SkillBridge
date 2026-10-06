import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US16SeleniumProjectChatTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            email='lead_us16@example.com', username='lead_us16', password='password123',
            role=Role.FREELANCER, is_email_verified=True, first_name='Lead', last_name='Dev'
        )
        self.client_user = User.objects.create_user(
            email='client_us16@example.com', username='client_us16', password='password123',
            role=Role.CLIENT, is_email_verified=True
        )
        self.project = Project.objects.create(
            client=self.client_user, freelancer=self.owner, title='Realtime Chat System',
            final_price=Decimal('2200.00'), deadline=timezone.now() + timezone.timedelta(days=12),
            status=Project.Status.ACTIVE
        )
        self.team = Team.objects.create(project=self.project, name='Chat Developers', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)

    def test_send_and_display_chat_message_in_browser(self):
        self.login_user('lead_us16@example.com', 'password123')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/chat/')
        time.sleep(1)

        # Locate chat input and send button
        input_el = self.driver.find_element(By.ID, 'chat-input')
        send_btn = self.driver.find_element(By.ID, 'chat-send-btn')

        test_message = 'Automated Selenium message test'
        input_el.send_keys(test_message)
        send_btn.click()
        time.sleep(2)

        # Verify message rendered in stream
        chat_stream = self.driver.find_element(By.ID, 'chat-messages')
        self.assertIn(test_message, chat_stream.text)