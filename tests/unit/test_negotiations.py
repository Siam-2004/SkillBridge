from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.proposals.models import Proposal
from apps.negotiations.models import Negotiation, Offer

class NegotiationUnitTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',username='siam',password='mominrifat2211',role=Role.CLIENT,first_name='Kamrul Hasan',last_name='Siam'
        )
        self.freelancer = User.objects.create_user(
            email='mominrifat8@gmail.com',username='rifat',password='mominrifat2211',role=Role.FREELANCER,first_name='Momin',last_name='Rifat'
        )
        self.category = Category.objects.create(name='Marketing', slug='marketing')
        self.job = Job.objects.create(
            client=self.client_user,title='SEO Optimization',category=self.category,description='On-page and technical SEO.',budget=Decimal('500.00'),deadline=timezone.now() + timezone.timedelta(days=20),status=Job.Status.OPEN,budget_reserved_at=timezone.now()
        )
        self.proposal = Proposal.objects.create(
            job=self.job,freelancer=self.freelancer,cover_letter='SEO expert with proven results.',proposed_amount=Decimal('450.00'),estimated_days=10
        )

    def test_negotiation_creation(self):
        negotiation = Negotiation.objects.create(
            job=self.job,proposal=self.proposal,client=self.client_user,freelancer=self.freelancer,status=Negotiation.Status.ACTIVE
        )
        self.assertTrue(negotiation.is_active)
        self.assertEqual(negotiation.other_party(self.client_user), self.freelancer)
        self.assertEqual(negotiation.other_party(self.freelancer), self.client_user)

    def test_offer_creation_and_counter(self):
        negotiation = Negotiation.objects.create(
            job=self.job,proposal=self.proposal,client=self.client_user,freelancer=self.freelancer,status=Negotiation.Status.ACTIVE
        )
        offer1 = Offer.objects.create(
            negotiation=negotiation,sender=self.client_user,receiver=self.freelancer,round_number=1,amount=Decimal('400.00'),deadline=timezone.now() + timezone.timedelta(days=10),status=Offer.Status.ACTIVE
        )
        self.assertEqual(offer1.amount, Decimal('400.00'))
        self.assertEqual(offer1.status, Offer.Status.ACTIVE)

        # Counter-offer from freelancer
        offer1.status = Offer.Status.COUNTERED
        offer1.save()
        offer2 = Offer.objects.create(
            negotiation=negotiation,sender=self.freelancer,receiver=self.client_user,
            round_number=2,amount=Decimal('425.00'),deadline=timezone.now() + timezone.timedelta(days=10),status=Offer.Status.ACTIVE
        )
        self.assertEqual(offer2.amount, Decimal('425.00'))
        self.assertEqual(offer2.round_number, 2)
