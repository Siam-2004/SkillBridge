from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import WalletTransaction
from apps.wallets import ledger

User = get_user_model()

class US23EscrowReleaseAllocationTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='client_release',
            email='client_rel@test.com',
            password='Password123!',
            role='CLIENT'
        )
        self.freelancer = User.objects.create_user(
            username='freelancer_release',
            email='freelancer_rel@test.com',
            password='Password123!',
            role='FREELANCER'
        )

    def test_escrow_release_records_separate_transactions(self):
        """US-23: Approval releases exact escrow amount and records separate payment transactions."""
        client_wallet = self.client_user.wallet
        client_wallet.escrow_balance = Decimal('2000.00')
        client_wallet.save()

        freelancer_wallet = self.freelancer.wallet
        initial_freelancer_balance = freelancer_wallet.available_balance

        release_amount = Decimal('1500.00')

        # 1. Debit client escrow
        debit_tx = ledger.move(
            user=self.client_user,
            amount=release_amount,
            transaction_type=WalletTransaction.Type.PROJECT_PAYMENT,
            from_bucket=WalletTransaction.Bucket.ESCROW,
            to_bucket=WalletTransaction.Bucket.EXTERNAL,
            counterparty=self.freelancer,
            actor=self.client_user,
            description='Release escrow to freelancer'
        )

        # 2. Credit freelancer available
        credit_tx = ledger.move(
            user=self.freelancer,
            amount=release_amount,
            transaction_type=WalletTransaction.Type.PROJECT_PAYMENT,
            from_bucket=WalletTransaction.Bucket.EXTERNAL,
            to_bucket=WalletTransaction.Bucket.AVAILABLE,
            counterparty=self.client_user,
            actor=self.client_user,
            related=debit_tx,
            description='Payment received from escrow'
        )

        client_wallet.refresh_from_db()
        freelancer_wallet.refresh_from_db()

        self.assertEqual(client_wallet.escrow_balance, Decimal('500.00'))
        self.assertEqual(freelancer_wallet.available_balance, initial_freelancer_balance + release_amount)
        self.assertEqual(debit_tx.amount, release_amount)
        self.assertEqual(credit_tx.amount, release_amount)
        self.assertEqual(credit_tx.counterparty, self.client_user)
