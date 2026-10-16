from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Withdrawal
from apps.wallets import services
from apps.core.exceptions import ValidationFailed

User = get_user_model()

class US24WithdrawalRequestTest(TestCase):
    def setUp(self):
        self.freelancer = User.objects.create_user(
            username='mehrab',
            email='mehrab@example.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.freelancer.wallet.available_balance = Decimal('2000.00')
        self.freelancer.wallet.reserved_balance = Decimal('0.00')
        self.freelancer.wallet.save()

    def test_withdrawal_reserves_requested_amount(self):
        """US-24: Withdrawal reserves requested amount and prevents double spending."""
        wdr = services.request_withdrawal(
            user=self.freelancer,
            amount=Decimal('800.00'),
            payment_method=Withdrawal.Method.BKASH,
            account_number='01712917930',
            account_name='Mehrab User'
        )
        self.freelancer.wallet.refresh_from_db()
        self.assertEqual(self.freelancer.wallet.available_balance, Decimal('1200.00'))
        self.assertEqual(self.freelancer.wallet.reserved_balance, Decimal('800.00'))
        self.assertEqual(wdr.status, Withdrawal.Status.PENDING)

    def test_withdrawal_exceeding_balance_rejected(self):
        """US-24: Cannot withdraw more than available balance."""
        with self.assertRaises(ValidationFailed):
            services.request_withdrawal(
                user=self.freelancer,
                amount=Decimal('5000.00'),
                payment_method=Withdrawal.Method.BKASH,
                account_number='01712917930',
                account_name='Mehrab User'
            )