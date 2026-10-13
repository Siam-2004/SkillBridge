from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError
from apps.accounts.models import User, Role
from apps.core.money import ZERO
from apps.core.exceptions import FinancialError, InsufficientFunds
from apps.wallets.models import Wallet, WalletTransaction
from apps.wallets import ledger

class WalletUnitTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',
            username='siam',
            password='mominrifat2211',
            role=Role.CLIENT,
            first_name='Kamrul Hasan',
            last_name='Siam'
        )
        self.wallet = Wallet.objects.get(user=self.user)

    def test_wallet_initial_state(self):
        self.assertEqual(self.wallet.available_balance, ZERO)
        self.assertEqual(self.wallet.reserved_balance, ZERO)
        self.assertEqual(self.wallet.escrow_balance, ZERO)
        self.assertEqual(self.wallet.total, ZERO)
        self.assertFalse(self.wallet.is_frozen)

    def test_wallet_deposit_movement(self):
        txn = ledger.move(
            user=self.user,
            amount=Decimal('1000.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE,
            description='Test deposit'
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('1000.00'))
        self.assertEqual(self.wallet.total, Decimal('1000.00'))
        self.assertEqual(self.wallet.lifetime_deposited, Decimal('1000.00'))
        self.assertEqual(txn.status, WalletTransaction.Status.COMPLETED)

    def test_insufficient_funds_raises_error(self):
        with self.assertRaises(InsufficientFunds):
            ledger.move(
                user=self.user,
                amount=Decimal('500.00'),
                transaction_type=WalletTransaction.Type.WITHDRAWAL,
                from_bucket=WalletTransaction.Bucket.AVAILABLE,
                to_bucket=WalletTransaction.Bucket.EXTERNAL
            )

    def test_internal_bucket_transfer(self):
        ledger.move(
            user=self.user,
            amount=Decimal('500.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE
        )
        ledger.move(
            user=self.user,
            amount=Decimal('200.00'),
            transaction_type=WalletTransaction.Type.BUDGET_RESERVATION,
            from_bucket=WalletTransaction.Bucket.AVAILABLE,
            to_bucket=WalletTransaction.Bucket.RESERVED
        )
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.available_balance, Decimal('300.00'))
        self.assertEqual(self.wallet.reserved_balance, Decimal('200.00'))
        self.assertEqual(self.wallet.total, Decimal('500.00'))

    def test_frozen_wallet_blocks_outgoing_movement(self):
        ledger.move(
            user=self.user,
            amount=Decimal('500.00'),
            transaction_type=WalletTransaction.Type.DEPOSIT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE
        )
        self.wallet.is_frozen = True
        self.wallet.frozen_reason = 'Suspicious activity'
        self.wallet.save()

        with self.assertRaises(FinancialError):
            ledger.move(
                user=self.user,
                amount=Decimal('100.00'),
                transaction_type=WalletTransaction.Type.WITHDRAWAL,
                from_bucket=WalletTransaction.Bucket.AVAILABLE,
                to_bucket=WalletTransaction.Bucket.EXTERNAL
            )
