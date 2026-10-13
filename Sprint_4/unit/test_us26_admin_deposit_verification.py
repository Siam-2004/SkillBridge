from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Deposit
from apps.wallets import services

User = get_user_model()

class US26AdminDepositVerificationTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='finance_admin',
            email='admin@test.com',
            password='Password123!',
            role='ADMIN'
        )
        self.client_user = User.objects.create_user(
            username='deposit_client2',
            email='client2@test.com',
            password='Password123!',
            role='CLIENT'
        )

    def test_admin_approve_deposit_credits_wallet_once(self):
        """US-26: Approval credits wallet exactly once and records audit."""
        deposit = services.create_deposit(
            user=self.client_user,
            amount=Decimal('800.00'),
            payment_method=Deposit.Method.BKASH,
            sender_number='01999888777',
            transaction_id='TXN888'
        )
        old_balance = self.client_user.wallet.available_balance
        approved = services.approve_deposit(deposit=deposit, admin_user=self.admin_user)
        self.assertEqual(approved.status, Deposit.Status.APPROVED)
        self.assertEqual(approved.reviewed_by, self.admin_user)
        self.assertIsNotNone(approved.approved_at)
        
        self.client_user.wallet.refresh_from_db()
        self.assertEqual(self.client_user.wallet.available_balance, old_balance + Decimal('800.00'))

    def test_admin_reject_deposit_stores_reason(self):
        """US-26: Rejection stores reason and does not credit wallet."""
        deposit = services.create_deposit(
            user=self.client_user,
            amount=Decimal('600.00'),
            payment_method=Deposit.Method.NAGAD,
            sender_number='01999888777',
            transaction_id='INVALID_TXN'
        )
        old_balance = self.client_user.wallet.available_balance
        rejected = services.reject_deposit(deposit=deposit, admin_user=self.admin_user, reason='Fake TrxID')
        self.assertEqual(rejected.status, Deposit.Status.REJECTED)
        self.assertEqual(rejected.admin_note, 'Fake TrxID')
        self.assertEqual(rejected.reviewed_by, self.admin_user)
        
        self.client_user.wallet.refresh_from_db()
        self.assertEqual(self.client_user.wallet.available_balance, old_balance)
