from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.proposals.models import Proposal

class ProposalUnitTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',username='siam',password='mominrifat2211',role=Role.CLIENT,first_name='Kamrul Hasan',last_name='Siam'
        )
        self.freelancer = User.objects.create_user(
            email='mominrifat8@gmail.com',username='rifat',password='mominrifat2211',role=Role.FREELANCER,first_name='Momin',last_name='Rifat'
        )
        self.category = Category.objects.create(name='Design', slug='design')
        self.job = Job.objects.create(
            client=self.client_user,title='UI/UX Design for Mobile App',category=self.category,
            description='Mobile app UI design in Figma.',budget=Decimal('300.00'),
            deadline=timezone.now() + timezone.timedelta(days=14),status=Job.Status.OPEN,budget_reserved_at=timezone.now()
        )

    def test_proposal_submission_and_defaults(self):
        proposal = Proposal.objects.create(
            job=self.job,freelancer=self.freelancer,cover_letter='I have 5 years experience designing Figma prototypes.',proposed_amount=Decimal('280.00'),estimated_days=5
        )
        self.assertEqual(proposal.status, Proposal.Status.SUBMITTED)
        self.assertTrue(proposal.is_open)
        self.assertTrue(proposal.can_withdraw)
        self.assertEqual(proposal.proposed_amount, Decimal('280.00'))

    def test_proposal_withdraw(self):
        proposal = Proposal.objects.create(
            job=self.job,freelancer=self.freelancer,cover_letter='Withdrawing soon.',proposed_amount=Decimal('250.00'),estimated_days=3
        )
        proposal.status = Proposal.Status.WITHDRAWN
        proposal.save()
        self.assertFalse(proposal.is_open)
        self.assertFalse(proposal.can_withdraw)

    def test_unique_active_proposal_per_job(self):
        Proposal.objects.create(
            job=self.job,freelancer=self.freelancer,cover_letter='First proposal.',proposed_amount=Decimal('250.00'),estimated_days=4
        )
        # Attempting second active proposal for same freelancer on same job
        with self.assertRaises(IntegrityError):
            Proposal.objects.create(
                job=self.job,freelancer=self.freelancer,cover_letter='Duplicate proposal.',proposed_amount=Decimal('200.00'),estimated_days=4
            )
