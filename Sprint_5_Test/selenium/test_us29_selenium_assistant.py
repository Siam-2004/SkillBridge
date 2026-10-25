import time
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By
from apps.projects.models import Project
from apps.tasks.models import Task
from Sprint_5_Test.selenium.base import BaseSprint5SeleniumTestCase

User = get_user_model()

class US29SeleniumAssistantTest(BaseSprint5SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.freelancer = User.objects.create_user(
            username='sel_ai_free',
            email='sel_ai_free@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.client_user = User.objects.create_user(
            username='sel_ai_client',
            email='sel_ai_client@test.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )

        self.project = Project.objects.create(
            client=self.client_user,
            freelancer=self.freelancer,
            title='NextGen AI Assistant Project',
            final_price=Decimal('12000.00'),
            deadline=timezone.now() + timedelta(days=25),
            status=Project.Status.IN_PROGRESS
        )

        self.task = Task.objects.create(
            project=self.project,
            title='Build Grounded Semantic Pipeline',
            created_by=self.client_user,
            assigned_to=self.freelancer,
            skillcoin_allocation=Decimal('3500.00'),
            priority=Task.Priority.HIGH,
            status=Task.Status.IN_PROGRESS,
            deadline=timezone.now() + timedelta(days=7)
        )

    def test_assistant_chat_interface_in_browser(self):
        """US-29: User visits AI Assistant chat interface and queries assigned tasks."""
        self.login_user('sel_ai_free@test.com', self.password)
        assistant_url = f'{self.live_server_url}/assistant/'
        self.driver.get(assistant_url)
        time.sleep(1)

        # Verify page header
        header = self.driver.find_element(By.CSS_SELECTOR, '.assistant-header-titles h2')
        self.assertIn('Assistant', header.text)

        # Input query
        input_field = self.driver.find_element(By.ID, 'userInput')
        input_field.send_keys('What tasks are assigned to me?')

        send_btn = self.driver.find_element(By.ID, 'sendBtn')
        send_btn.click()
        time.sleep(2.5)

        # Confirm answer appears in chat window
        chat_box = self.driver.find_element(By.ID, 'chatMessages')
        self.assertIn('Build Grounded Semantic Pipeline', chat_box.text)
