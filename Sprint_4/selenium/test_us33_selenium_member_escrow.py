import os

import tempfile
import time
from decimal import Decimal
from datetime import timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from django.utils import timezone
from django.contrib.auth import get_user_model
from Sprint_4.selenium.base import BaseSprint4SeleniumTestCase
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as task_services
from apps.tasks.models import Task

User = get_user_model()

class US33SeleniumMemberEscrowPaymentTest(BaseSprint4SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.client_user = User.objects.create_user(
            username='mehrab',
            email='mehrab@test.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )
        self.leader = User.objects.create_user(
            username='siam',
            email='siam@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.member = User.objects.create_user(
            username='rifat',
            email='rifat@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.client_user.wallet.available_balance = Decimal('5000.00')
        self.client_user.wallet.escrow_balance = Decimal('1200.00')
        self.client_user.wallet.save()

        self.project = Project.objects.create(
            client=self.client_user,
            freelancer=self.leader,
            title='Selenium Team Workspace',
            final_price=Decimal('1200.00'),
            deadline=timezone.now() + timedelta(days=10)
        )
        self.team = Team.objects.create(
            project=self.project,
            name='Alpha Team',
            owner=self.leader
        )
        TeamMember.objects.create(team=self.team, user=self.leader, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=self.team, user=self.member, role=TeamMember.Role.MEMBER)

        self.task = task_services.create_task(
            project=self.project,
            title='Implement API Endpoint',
            created_by=self.leader,
            assigned_to=self.member,
            skillcoin_allocation=Decimal('450.00')
        )

    def test_member_delivers_file_and_leader_approves_escrow_payment(self):
        """US-33: Member uploads deliverable in browser, submits review, leader clicks Approve & Pay."""
        initial_member_balance = self.member.wallet.available_balance

        # 1. Member logs in and opens the project workspace
        self.login_user('rifat@test.com', self.password)
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)

        # 2. Member uploads deliverable file
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"Completed API code implementation deliverable.")
            temp_path = f.name

        try:
            file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"][name="file"]')
            file_input.send_keys(temp_path)
            upload_btn = self.driver.find_element(By.XPATH, '//button[contains(text(), "Upload Deliverable")]')
            upload_btn.click()
            time.sleep(1.5)

            # 3. Member submits task for review
            status_select_el = self.driver.find_element(By.CSS_SELECTOR, f'form[action*="/tasks/{self.task.id}/status/"] select[name="status"]')
            Select(status_select_el).select_by_value('IN_REVIEW')
            time.sleep(1.5)

            self.task.refresh_from_db()
            self.assertEqual(self.task.status, Task.Status.IN_REVIEW)

            # 4. Leader logs in to review and approve
            self.login_user('siam@test.com', self.password)
            self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
            time.sleep(1)

            # Leader sees deliverable file link
            self.assertIn('deliverables', self.driver.page_source.lower())

            # Leader clicks 'Approve & Pay'
            approve_btn = self.driver.find_element(By.XPATH, '//button[contains(text(), "Approve & Pay")]')
            approve_btn.click()
            time.sleep(1.5)

            # 5. Verify task is completed and escrow payment credited to member
            self.task.refresh_from_db()
            self.assertEqual(self.task.status, Task.Status.COMPLETED)

            self.member.wallet.refresh_from_db()
            self.assertEqual(self.member.wallet.available_balance, initial_member_balance + Decimal('450.00'))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)