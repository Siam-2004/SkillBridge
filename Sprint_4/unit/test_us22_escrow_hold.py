<<<<<<< HEAD
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import WalletTransaction
from apps.wallets import ledger

User = get_user_model()

class US22EscrowHoldAtomicTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='escrow_client',
            email='23101199.com',
            password='Password123!',
            role='CLIENT'
        )

    def test_escrow_hold_moves_funds_atomically(self):
        """US-22: Accepted project moves exact agreed amount from available to escrow atomically."""
        wallet = self.client_user.wallet
        wallet.available_balance = Decimal('3000.00')
        wallet.escrow_balance = Decimal('0.00')
        wallet.save()

        # Hold 1200 into escrow
        tx = ledger.move(
            user=self.client_user,
            amount=Decimal('1200.00'),
            transaction_type=WalletTransaction.Type.ESCROW_HOLD,
            from_bucket=WalletTransaction.Bucket.AVAILABLE,
            to_bucket=WalletTransaction.Bucket.ESCROW,
            actor=self.client_user,
            description='Escrow hold for project'
        )

        wallet.refresh_from_db()
        self.assertEqual(wallet.available_balance, Decimal('1800.00'))
        self.assertEqual(wallet.escrow_balance, Decimal('1200.00'))
        self.assertEqual(tx.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(tx.delta, Decimal('0.00'))  # Internal movement between buckets
=======
from decimal import Decimal
>>>>>>> 9739d3368194f84a782517d152378c7444626916
