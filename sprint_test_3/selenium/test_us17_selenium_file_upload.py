import os
import tempfile
import time
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from selenium.webdriver.common.by import By
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.projects.models import Project, Team, TeamMember
from apps.projects import services as ps
from sprint_test_3.selenium.base import BaseSprint3SeleniumTestCase

class US17SeleniumFileUploadTestCase(BaseSprint3SeleniumTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(email='l17@ex.com', username='lead_us17', password='p', role=Role.FREELANCER, is_email_verified=True)
        c = User.objects.create_user(email='c17@ex.com', username='client_us17', password='p', role=Role.CLIENT, is_email_verified=True)
        self.member = User.objects.create_user(email='m17@ex.com', username='member_us17', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.outsider = User.objects.create_user(email='x17@ex.com', username='outsider_us17', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.project = Project.objects.create(client=c, freelancer=self.owner, title='File Sharing Project', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.project, name='File Team', owner=self.owner)
        TeamMember.objects.create(team=t, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.member, role=TeamMember.Role.MEMBER)

    def test_upload_file_in_browser(self):
        self.login_user('lead_us17', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b"Deliverable release v1.0")
            tmp_path = tmp.name
        try:
            self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/files/upload/"] input[type="file"]').send_keys(tmp_path)
            self.driver.find_element(By.CSS_SELECTOR, 'form[action*="/files/upload/"] button[type="submit"]').click()
            time.sleep(1.5)
            self.assertIn(os.path.basename(tmp_path), self.driver.page_source)
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

    def test_unauthorized_user_denied_file_download_in_browser(self):
        f = SimpleUploadedFile("confidential.pdf", b"secret", content_type="application/pdf")
        pf = ps.upload_project_file(self.project, self.owner, f)
        self.login_user('outsider_us17', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/files/{pf.id}/download/')
        time.sleep(1)
        self.assertTrue('403' in self.driver.page_source or 'Access Denied' in self.driver.page_source or 'Forbidden' in self.driver.page_source)

    def test_authorized_team_member_sees_download_link_in_browser(self):
        f = SimpleUploadedFile("specs.pdf", b"spec content", content_type="application/pdf")
        ps.upload_project_file(self.project, self.owner, f)
        self.login_user('member_us17', 'p')
        self.driver.get(f'{self.live_server_url}/projects/{self.project.public_id}/')
        time.sleep(1)
        self.assertIn('specs.pdf', self.driver.page_source)
        self.assertIn('Download', self.driver.page_source)
