from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.agreements import services as agreement_services
from apps.agreements.models import Agreement
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets import ledger

class DeliveryAndPayoutIntegrationTestCase(TestCase):
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
        self.category = Category.objects.create(name='QA & Testing', slug='qa-testing')

        # Fund client wallet and reserve 500 SKC for job
        ledger.move(
            user=self.client_user,
            amount=Decimal('500.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.RESERVED
        )

        self.job = Job.objects.create(
            client=self.client_user,
            hired_freelancer=self.freelancer,
            title='Automated Test Suite for API',
            category=self.category,
            description='Write unit and integration tests.',
            budget=Decimal('500.00'),
            reserved_amount=Decimal('500.00'),
            deadline=timezone.now() + timezone.timedelta(days=10),
            status=Job.Status.HIRED,
            budget_reserved_at=timezone.now()
        )

        self.agreement = Agreement.objects.create(
            job=self.job,
            client=self.client_user,
            freelancer=self.freelancer,
            amount=Decimal('500.00'),
            deadline=timezone.now() + timezone.timedelta(days=10),
            deliverables='100% test coverage report and scripts',
            status=Agreement.Status.ACTIVE
        )

    def test_complete_work_submission_approval_and_payout_flow(self):
        # 1. Freelancer submits deliverables
        agreement = agreement_services.submit_work(
            agreement=self.agreement,
            freelancer=self.freelancer,
            submission_text='The full test suite has been completed and verified.',
            submission_link='https://github.com/example/api-tests'
        )
        self.assertTrue(agreement.has_submitted_work)
        self.assertEqual(agreement.status, Agreement.Status.IN_PROGRESS)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.IN_PROGRESS)

        # 2. Client approves deliverables and releases payment
        completed_agreement = agreement_services.complete_agreement_and_release_payment(
            agreement=agreement,
            client=self.client_user,
            feedback='Outstanding quality, everything runs cleanly!'
        )
        self.assertTrue(completed_agreement.is_completed)
        self.assertEqual(completed_agreement.status, Agreement.Status.COMPLETED)
        self.assertEqual(completed_agreement.client_feedback, 'Outstanding quality, everything runs cleanly!')

        # 3. Check wallet balances
        client_wallet = Wallet.objects.get(user=self.client_user)
        self.assertEqual(client_wallet.reserved_balance, Decimal('0.00'))

        freelancer_wallet = Wallet.objects.get(user=self.freelancer)
        self.assertEqual(freelancer_wallet.available_balance, Decimal('500.00'))
        self.assertEqual(freelancer_wallet.lifetime_earned, Decimal('500.00'))

        # 4. Check job status is COMPLETED
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.COMPLETED)
        self.assertIsNotNone(self.job.completed_at)
