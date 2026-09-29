from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.core.exceptions import ValidationFailed, InsufficientFunds
from apps.marketplace.models import Job
from apps.marketplace import services
from apps.profiles.models import Category, Skill
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets import ledger

class MarketplaceUnitTestCase(TestCase):
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
        self.category = Category.objects.create(name='Web Development', slug='web-dev')
        self.skill = Skill.objects.create(name='Django', slug='django')

    def test_job_creation_with_any_positive_budget(self):
        # Verify that low budgets (e.g. 25 SKC) work without 500 limit
        future_date = timezone.now() + timezone.timedelta(days=10)
        job = services.create_job(
            client=self.client_user,
            title='Build a small landing page',
            category=self.category,
            description='A quick responsive landing page.',
            budget=Decimal('25.00'),
            deadline=future_date,
            skills=[self.skill],
            publish=False
        )
        self.assertEqual(job.budget, Decimal('25.00'))
        self.assertEqual(job.status, Job.Status.DRAFT)
        self.assertIn(self.skill, job.skills.all())

    def test_job_creation_fails_for_past_deadline(self):
        past_date = timezone.now() - timezone.timedelta(days=1)
        with self.assertRaises(ValidationFailed):
            services.create_job(
                client=self.client_user,
                title='Invalid Deadline Job',
                category=self.category,
                description='Past deadline should fail.',
                budget=Decimal('100.00'),
                deadline=past_date,
                publish=False
            )

    def test_publish_job_reserves_budget_from_wallet(self):
        # Deposit 200 into client wallet
        ledger.move(
            user=self.client_user,
            amount=Decimal('200.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE
        )

        future_date = timezone.now() + timezone.timedelta(days=7)
        job = services.create_job(
            client=self.client_user,
            title='Design a Logo',
            category=self.category,
            description='Vector logo for new startup.',
            budget=Decimal('150.00'),
            deadline=future_date,
            publish=True
        )
        self.assertEqual(job.status, Job.Status.OPEN)
        self.assertEqual(job.reserved_amount, Decimal('150.00'))

        wallet = Wallet.objects.get(user=self.client_user)
        self.assertEqual(wallet.available_balance, Decimal('50.00'))
        self.assertEqual(wallet.reserved_balance, Decimal('150.00'))

    def test_publish_job_fails_when_funds_insufficient(self):
        future_date = timezone.now() + timezone.timedelta(days=7)
        job = services.create_job(
            client=self.client_user,
            title='Unfunded Job',
            category=self.category,
            description='Client has no funds in wallet.',
            budget=Decimal('300.00'),
            deadline=future_date,
            publish=False
        )
        with self.assertRaises(InsufficientFunds):
            services.publish_job(job=job, client=self.client_user)

    def test_cancel_job_releases_reserved_budget(self):
        ledger.move(
            user=self.client_user,
            amount=Decimal('100.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE
        )
        job = services.create_job(
            client=self.client_user,
            title='Job to Cancel',
            category=self.category,
            description='Will be cancelled.',
            budget=Decimal('100.00'),
            deadline=timezone.now() + timezone.timedelta(days=5),
            publish=True
        )
        wallet = Wallet.objects.get(user=self.client_user)
        self.assertEqual(wallet.available_balance, Decimal('0.00'))
        self.assertEqual(wallet.reserved_balance, Decimal('100.00'))

        from unittest.mock import patch
        with patch('apps.marketplace.services.notify_many'):
            services.cancel_job(job=job, client=self.client_user, reason='Changed my mind')
        wallet.refresh_from_db()
        self.assertEqual(wallet.available_balance, Decimal('100.00'))
        self.assertEqual(wallet.reserved_balance, Decimal('0.00'))
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.CANCELLED)