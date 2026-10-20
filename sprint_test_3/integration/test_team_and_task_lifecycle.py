from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, Client
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.agreements.models import Agreement
from apps.projects.models import TeamInvitation
from apps.tasks.models import Task, Subtask, TaskActivity
from apps.projects import services as ps
from apps.tasks import services as ts
from apps.notifications import triggers

class Sprint3TeamAndTaskLifecycleIntegrationTestCase(TestCase):
    def setUp(self):
        self.http_client = Client()
        self.c_user = User.objects.create_user(email='c@corp.com', username='client_ceo', password='p', role=Role.CLIENT, is_email_verified=True)
        self.lead = User.objects.create_user(email='l@fl.org', username='team_lead', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.fe = User.objects.create_user(email='fe@fl.org', username='frontend_pro', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.qa = User.objects.create_user(email='qa@fl.org', username='qa_engineer', password='p', role=Role.FREELANCER, is_email_verified=True)
        self.ext = User.objects.create_user(email='x@ext.org', username='random_user', password='p', role=Role.FREELANCER, is_email_verified=True)
        cat = Category.objects.create(name='Eng', slug='eng')
        self.job = Job.objects.create(client=self.c_user, hired_freelancer=self.lead, title='Platform', category=cat, budget=Decimal('5000'), deadline=timezone.now()+timezone.timedelta(days=30), status=Job.Status.HIRED)
        self.agreement = Agreement.objects.create(job=self.job, client=self.c_user, freelancer=self.lead, amount=Decimal('5000'), deadline=timezone.now()+timezone.timedelta(days=30), deliverables='Suite', status=Agreement.Status.ACTIVE)

    def test_complete_sprint_3_collaboration_workflow(self):
        # US-12
        p = ps.create_project_from_agreement(self.agreement)
        self.assertEqual(p.team.owner, self.lead)
        inv_fe = ps.invite_to_team(p.team, self.fe, self.lead)
        triggers.trigger_team_invitation_email(inv_fe)
        inv_qa = ps.invite_to_team(p.team, self.qa, self.lead)
        triggers.trigger_team_invitation_email(inv_qa)
        ps.respond_to_invitation(inv_fe, self.fe, True)
        ps.respond_to_invitation(inv_qa, self.qa, True)
        self.assertEqual(p.team.members.count(), 3)
        self.assertTrue(p.has_access(self.fe))
        self.assertFalse(p.has_access(self.ext))

        # US-13 & US-14
        t = ts.create_task(p, 'UI Dev', '', self.lead, priority='HIGH')
        st1 = ts.create_subtask(t, 'Charts', '', self.lead, self.fe)
        triggers.trigger_task_assigned_email(st1, self.lead)
        st2 = ts.create_subtask(t, 'Tests', '', self.lead, self.qa)
        triggers.trigger_task_assigned_email(st2, self.lead)
        ts.update_subtask_status(st1, Subtask.Status.COMPLETED, self.fe)
        ts.update_subtask_status(st2, Subtask.Status.COMPLETED, self.qa)
        t.refresh_from_db()
        self.assertEqual(t.status, Task.Status.COMPLETED)

        # US-15
        self.assertGreaterEqual(TaskActivity.objects.filter(project=p).count(), 3)

        # US-16
        self.http_client.force_login(self.fe)
        self.assertEqual(self.http_client.post(f'/projects/{p.public_id}/chat/send/', {'content': 'Done!'}).status_code, 200)
        self.http_client.force_login(self.qa)
        poll = self.http_client.get(f'/projects/{p.public_id}/chat/poll/?after_id=0').json()
        self.assertEqual(poll['messages'][-1]['author'], 'frontend_pro')

        # US-17
        f = SimpleUploadedFile("rep.pdf", b"%PDF-1.4 report", content_type="application/pdf")
        pf = ps.upload_project_file(p, self.fe, f)
        self.assertEqual(self.http_client.get(f'/projects/{p.public_id}/files/{pf.id}/download/').status_code, 200)
        self.http_client.force_login(self.ext)
        self.assertEqual(self.http_client.get(f'/projects/{p.public_id}/files/{pf.id}/download/').status_code, 403)

        # US-18 & US-19
        cmt = ps.add_project_comment(p, self.qa, 'Good @frontend_pro on #1', t)
        self.assertIn(self.fe, cmt.mentions.all())
        self.assertGreaterEqual(len(mail.outbox), 3)
