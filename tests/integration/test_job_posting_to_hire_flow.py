from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.marketplace import services as market_services
from apps.profiles.models import Category
from apps.proposals import services as proposal_services
from apps.proposals.models import Proposal
from apps.negotiations.models import Negotiation, Offer
from apps.agreements import services as agreement_services
from apps.agreements.models import Agreement
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets import ledger

class JobPostingToHireIntegrationTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',
            username='siam',
            password='mominrifat2211',
            role=Role.CLIENT,
            is_email_verified=True,
            first_name='Kamrul Hasan',
            last_name='Siam'
        )
        self.freelancer = User.objects.create_user(
            email='mominrifat8@gmail.com',
            username='rifat',
            password='mominrifat2211',
            role=Role.FREELANCER,
            is_email_verified=True,
            first_name='Momin',
            last_name='Rifat'
        )
        self.category = Category.objects.create(name='DevOps', slug='devops')

    def test_end_to_end_job_posting_to_hire_flow(self):
        # 1. Client deposits 1000 SKC into wallet
        ledger.move(
            user=self.client_user,
            amount=Decimal('1000.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE
        )
        client_wallet = Wallet.objects.get(user=self.client_user)
        self.assertEqual(client_wallet.available_balance, Decimal('1000.00'))

        # 2. Client creates and publishes a job for 600 SKC
        job = market_services.create_job(
            client=self.client_user,
            title='Setup Kubernetes Cluster and CI/CD',
            category=self.category,
            description='Deploy production cluster with GitLab pipelines.',
            budget=Decimal('600.00'),
            deadline=timezone.now() + timezone.timedelta(days=15),
            publish=True
        )
        self.assertEqual(job.status, Job.Status.OPEN)

        # Verify Client's wallet reserved the job budget
        client_wallet.refresh_from_db()
        self.assertEqual(client_wallet.available_balance, Decimal('400.00'))
        self.assertEqual(client_wallet.reserved_balance, Decimal('600.00'))

        # 3. Freelancer submits a proposal for 600 SKC
        proposal = proposal_services.submit_proposal(
            job=job,
            freelancer=self.freelancer,
            cover_letter='I am a Certified Kubernetes Administrator with 6+ years DevOps experience.',
            proposed_amount=Decimal('600.00'),
            estimated_days=7,
            deliverables='Helm charts, Terraform files, CI/CD pipeline'
        )
        self.assertEqual(proposal.status, Proposal.Status.SUBMITTED)
        job.refresh_from_db()
        self.assertEqual(job.proposal_count, 1)

        # 4. Client accepts terms via offer & creates Agreement
        negotiation = Negotiation.objects.create(
            job=job,
            proposal=proposal,
            client=self.client_user,
            freelancer=self.freelancer,
            status=Negotiation.Status.ACTIVE
        )
        offer = Offer.objects.create(
            negotiation=negotiation,
            sender=self.client_user,
            receiver=self.freelancer,
            amount=Decimal('600.00'),
            deadline=timezone.now() + timezone.timedelta(days=10),
            deliverables='K8s cluster and CI/CD pipelines',
            status=Offer.Status.ACCEPTED
        )

        agreement = agreement_services.create_agreement_from_offer(offer=offer, actor=self.client_user)
        self.assertEqual(agreement.status, Agreement.Status.ACTIVE)
        self.assertEqual(agreement.amount, Decimal('600.00'))

        # 5. Check job and proposal status transitions
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.HIRED)
        self.assertEqual(job.hired_freelancer, self.freelancer)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, Proposal.Status.ACCEPTED)