from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.exceptions import InsufficientFunds
from apps.projects.models import Project
from apps.wallets import ledger
from apps.wallets.models import WalletTransaction

User = get_user_model()

class US22EscrowHoldTest(TestCase):
    def setUp(self):
        self.client = User.objects.create_user(
            username='sabbir_client',
            email='sabbir_client@example.com',
            password='Password123!',
            role='CLIENT'
        )
        self.freelancer = User.objects.create_user(
            username='sabbir_dev',
            email='sabbir_dev@example.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.client.wallet.available_balance = Decimal('5000.00')
        self.client.wallet.escrow_balance = Decimal('0.00')
        self.client.wallet.reserved_balance = Decimal('0.00')
        self.client.wallet.save()

        self.project = Project.objects.create(
            client=self.client,
            freelancer=self.freelancer,
            title='E-Commerce Platform Development',
            final_price=Decimal('1500.00'),
            deadline=timezone.now() + timezone.timedelta(days=14)
        )

    def test_accepted_project_moves_exact_amount_from_available_to_escrow_atomically(self):
        """US-22: Accepted project moves exact agreed amount from available to escrow atomically."""
        agreed_amount = Decimal('1500.00')

        txn = ledger.hold_escrow_from_available(
            user=self.client,
            amount=agreed_amount,
            project=self.project,
            actor=self.client
        )

        self.client.wallet.refresh_from_db()
        # Exact agreed amount deducted from available
        self.assertEqual(self.client.wallet.available_balance, Decimal('3500.00'))
        # Exact agreed amount credited to escrow
        self.assertEqual(self.client.wallet.escrow_balance, Decimal('1500.00'))
        # Total wallet balance remains conserved
        self.assertEqual(self.client.wallet.total, Decimal('5000.00'))

        # Verify atomic transaction record
        self.assertEqual(txn.transaction_type, WalletTransaction.Type.ESCROW_HOLD)
        self.assertEqual(txn.from_bucket, WalletTransaction.Bucket.AVAILABLE)
        self.assertEqual(txn.to_bucket, WalletTransaction.Bucket.ESCROW)
        self.assertEqual(txn.amount, agreed_amount)
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(txn.project_id, self.project.id)

    def test_insufficient_available_balance_rolls_back_atomically(self):
        """US-22: Cannot hold escrow if available balance is insufficient; atomic rollback preserves balances."""
        self.client.wallet.available_balance = Decimal('800.00')
        self.client.wallet.escrow_balance = Decimal('0.00')
        self.client.wallet.save()

        agreed_amount = Decimal('1500.00')
        initial_tx_count = WalletTransaction.objects.count()

        with self.assertRaises(InsufficientFunds):
            ledger.hold_escrow_from_available(
                user=self.client,
                amount=agreed_amount,
                project=self.project,
                actor=self.client
            )

        self.client.wallet.refresh_from_db()
        self.assertEqual(self.client.wallet.available_balance, Decimal('800.00'))
        self.assertEqual(self.client.wallet.escrow_balance, Decimal('0.00'))
        self.assertEqual(WalletTransaction.objects.count(), initial_tx_count)
