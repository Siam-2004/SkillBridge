import time
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By
from apps.projects.models import Project, Dispute
from Sprint_5_Test.selenium.base import BaseSprint5SeleniumTestCase

User = get_user_model()

class US27SeleniumDisputeTest(BaseSprint5SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.client_user = User.objects.create_user(
            username='sel_disp_client',
            email='sel_disp_client@test.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )
        self.freelancer = User.objects.create_user(
            username='sel_disp_free',
            email='sel_disp_free@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )

        self.project = Project.objects.create(
            client=self.client_user,
            freelancer=self.freelancer,
            title='Selenium Dispute In-Progress Project',
            final_price=Decimal('7000.00'),
            deadline=timezone.now() + timedelta(days=10),
            status=Project.Status.IN_PROGRESS
        )

    def test_submit_dispute_in_browser(self):
        """US-27: Freelancer opens dispute submission form and submits dispute."""
        self.login_user('sel_disp_free@test.com', self.password)
        project_url = f'{self.live_server_url}/projects/{self.project.public_id}/'
        self.driver.get(project_url)
        time.sleep(1)

        # Dispute section verification
        self.assertIn('Project Dispute Support', self.driver.page_source)
        
        # Click toggle button to reveal form
        toggle_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Raise Dispute')]")
        toggle_btn.click()
        time.sleep(0.5)

        form = self.driver.find_element(By.ID, 'dispute-form')
        reason_select = form.find_element(By.NAME, 'reason')
        reason_select.send_keys('Payment or milestone dispute')

        desc = form.find_element(By.NAME, 'description')
        desc.send_keys('Client requested extra uncontracted features and withheld payment approval.')

        file_dispute_btn = form.find_element(By.XPATH, "//button[contains(text(), 'Submit Dispute to Admin')]")
        file_dispute_btn.click()
        time.sleep(1.5)

        # Confirm dispute recorded in DB
        self.assertTrue(Dispute.objects.filter(project=self.project, raised_by=self.freelancer).exists())
