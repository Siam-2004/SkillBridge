from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.core.exceptions import PermissionDenied
from apps.projects.models import Project, Team, TeamMember
from apps.tasks import services as ts
from apps.projects import services as ps

class US17SecureFileUploadDownloadTestCase(TestCase):
    def setUp(self):
        c = User.objects.create_user(email='rifat1@gmail.com', username='client', password='rifat', role=Role.CLIENT, is_email_verified=True)
        self.own = User.objects.create_user(email='rifat2@gmail.com', username='own', password='rifat', role=Role.FREELANCER, is_email_verified=True)
        self.mem = User.objects.create_user(email='rifat3@gmail.com', username='mem', password='rifat', role=Role.FREELANCER, is_email_verified=True)
        self.out = User.objects.create_user(email='rifat4@gmail.com', username='out', password='rifat', role=Role.FREELANCER, is_email_verified=True)
        self.p = Project.objects.create(client=c, freelancer=self.own, title='P', final_price=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Project.Status.ACTIVE)
        t = Team.objects.create(project=self.p, name='T', owner=self.own)
        TeamMember.objects.create(team=t, user=self.own, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=t, user=self.mem, role=TeamMember.Role.MEMBER)
        self.cli = Client()

    def test_file_upload_download_security(self):
        f = SimpleUploadedFile("s.pdf", b"content", content_type="application/pdf")
        pf = ps.upload_project_file(self.p, self.own, f)
        self.cli.force_login(self.mem)
        self.assertEqual(self.cli.get(f'/projects/{self.p.public_id}/files/{pf.id}/download/').status_code, 200)
        self.cli.force_login(self.out)
        self.assertEqual(self.cli.get(f'/projects/{self.p.public_id}/files/{pf.id}/download/').status_code, 403)

    def test_task_file_security(self):
        t = ts.create_task(self.p, 'T', '', self.own)
        f = SimpleUploadedFile("c.env", b"KEY=1", content_type="text/plain")
        tf = ts.upload_task_file(t, self.own, f)
        self.cli.force_login(self.mem)
        self.assertEqual(self.cli.get(f'/tasks/{t.id}/files/{tf.id}/download/').status_code, 200)
        self.cli.force_login(self.out)
        self.assertEqual(self.cli.get(f'/tasks/{t.id}/files/{tf.id}/download/').status_code, 403)

    def test_unauthorized_upload_denied(self):
        f = SimpleUploadedFile("hack.sh", b"rm -rf", content_type="text/plain")
        with self.assertRaises(PermissionDenied): ps.upload_project_file(self.p, self.out, f)
