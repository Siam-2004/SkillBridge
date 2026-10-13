from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets import ledger

User = get_user_model()

class US20WalletAndTransactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wallet_user',
            email='wallet_user@test.com',
            password='Password123!',
            role='CLIENT'
        )

    def test_wallet_balance_buckets_exist(self):
        """US-20: Each user has available, escrow and reserved balances."""
        wallet = Wallet.objects.get(user=self.user)
        self.assertTrue(hasattr(wallet, 'available_balance'))
        self.assertTrue(hasattr(wallet, 'escrow_balance'))
        self.assertTrue(hasattr(wallet, 'reserved_balance'))
        self.assertEqual(wallet.total, wallet.available_balance + wallet.escrow_balance + wallet.reserved_balance)

    def test_immutable_financial_transaction_created_on_movement(self):
        """US-20: Every balance-changing operation creates a transaction record."""
        initial_tx_count = WalletTransaction.objects.filter(user=self.user).count()
        ledger.credit_deposit(user=self.user, amount=Decimal('500.00'), deposit=None, actor=self.user)
        new_tx_count = WalletTransaction.objects.filter(user=self.user).count()
        self.assertEqual(new_tx_count, initial_tx_count + 1)
        tx = WalletTransaction.objects.filter(user=self.user).latest('created_at')
        self.assertEqual(tx.amount, Decimal('500.00'))
        self.assertEqual(tx.to_bucket, WalletTransaction.Bucket.AVAILABLE)
        self.assertEqual(tx.status, WalletTransaction.Status.COMPLETED)
