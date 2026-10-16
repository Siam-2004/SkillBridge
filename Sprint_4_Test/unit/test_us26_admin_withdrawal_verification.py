from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Withdrawal
from apps.wallets import services

User = get_user_model()

class US26AdminWithdrawalVerificationTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_wdr',
            email='admin_wdr@test.com',
            password='Password123!',
            role='ADMIN'
        )
        self.freelancer = User.objects.create_user(
            username='freelancer_payout',
            email='freelancer_payout@test.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.freelancer.wallet.available_balance = Decimal('1000.00')
        self.freelancer.wallet.save()

    def test_admin_approve_withdrawal_with_external_trxid(self):
        """US-26: Admin can complete withdrawal and record outgoing TrxID."""
        wdr = services.request_withdrawal(
            user=self.freelancer,
            amount=Decimal('400.00'),
            payment_method=Withdrawal.Method.BKASH,
            account_number='01811223344'
        )
        approved_wdr = services.approve_withdrawal(
            withdrawal=wdr,
            admin_user=self.admin_user,
            transaction_id='BKASH_OUT_5566'
        )
        self.assertEqual(approved_wdr.status, Withdrawal.Status.APPROVED)
        self.assertEqual(approved_wdr.external_transaction_id, 'BKASH_OUT_5566')
        self.assertEqual(approved_wdr.reviewed_by, self.admin_user)
        
        self.freelancer.wallet.refresh_from_db()
        self.assertEqual(self.freelancer.wallet.reserved_balance, Decimal('0.00'))
        self.assertEqual(self.freelancer.wallet.lifetime_withdrawn, Decimal('400.00'))

    def test_admin_reject_withdrawal_reverses_funds_to_available(self):
        """US-26: Admin rejection reverses reserved funds back to available."""
        wdr = services.request_withdrawal(
            user=self.freelancer,
            amount=Decimal('300.00'),
            payment_method=Withdrawal.Method.NAGAD,
            account_number='01811223344'
        )
        rejected_wdr = services.reject_withdrawal(
            withdrawal=wdr,
            admin_user=self.admin_user,
            reason='Invalid phone number'
        )
        self.assertEqual(rejected_wdr.status, Withdrawal.Status.REJECTED)
        self.assertEqual(rejected_wdr.admin_note, 'Invalid phone number')
        
        self.freelancer.wallet.refresh_from_db()
        self.assertEqual(self.freelancer.wallet.reserved_balance, Decimal('0.00'))
        self.assertEqual(self.freelancer.wallet.available_balance, Decimal('1000.00'))