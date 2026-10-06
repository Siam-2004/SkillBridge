from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.agreements.models import Agreement
from apps.projects.models import TeamInvitation
from apps.projects import services as ps

class US12TeamModelsAndInviteTestCase(TestCase):
    def setUp(self):
        self.c = User.objects.create_user(email='rifat1@gmail.com', username='client', password='r', role=Role.CLIENT, is_email_verified=True)
        self.hf = User.objects.create_user(email='rifat2@gmail.com', username='lead', password='r', role=Role.FREELANCER, is_email_verified=True)
        self.inv = User.objects.create_user(email='rifat3@gmail.com', username='inv', password='r', role=Role.FREELANCER, is_email_verified=True)
        cat = Category.objects.create(name='Rifat', slug='rifat')
        job = Job.objects.create(client=self.c, title='J', category=cat, budget=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), status=Job.Status.HIRED)
        self.agr = Agreement.objects.create(job=job, client=self.c, freelancer=self.hf, amount=Decimal('100'), deadline=timezone.now()+timezone.timedelta(days=1), deliverables='D', status=Agreement.Status.ACTIVE)

    def test_team_creation_and_invitation(self):
        p = ps.create_project_from_agreement(self.agr)
        self.assertEqual(p.team.owner, self.hf)
        self.assertIn(self.inv, ps.search_freelancers('inv', exclude_team=p.team))
        inv1 = ps.invite_to_team(p.team, self.inv, self.hf)
        self.assertEqual(inv1.status, TeamInvitation.Status.PENDING)
        ps.respond_to_invitation(inv1, self.inv, True)
        self.assertTrue(p.team.is_member(self.inv))

    def test_invitation_decline(self):
        p = ps.create_project_from_agreement(self.agr)
        inv2 = ps.invite_to_team(p.team, self.inv, self.hf)
        ps.respond_to_invitation(inv2, self.inv, False)
        self.assertEqual(inv2.status, TeamInvitation.Status.DECLINED)
        self.assertFalse(p.team.is_member(self.inv))

    def test_already_member_invite_rejected(self):
        p = ps.create_project_from_agreement(self.agr)
        with self.assertRaises(ValidationFailed): ps.invite_to_team(p.team, self.hf, self.hf)

    def test_unauthorized_user_cannot_invite(self):
        p = ps.create_project_from_agreement(self.agr)
        with self.assertRaises(PermissionDenied): ps.invite_to_team(p.team, self.inv, self.inv)
