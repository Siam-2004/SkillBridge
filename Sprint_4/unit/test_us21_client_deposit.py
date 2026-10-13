from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.wallets.models import Deposit
from apps.wallets.forms import DepositForm
from apps.wallets import services

User = get_user_model()

class US21ClientDepositTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='deposit_client',
            email='deposit_client@test.com',
            password='Password123!',
            role='CLIENT'
        )

    def test_deposit_form_submission(self):
        """US-21: Client can submit amount, method and external TrxID."""
        form_data = {
            'amount': '1500.00',
            'payment_method': Deposit.Method.BKASH,
            'sender_number': '01711223344',
            'transaction_id': 'BK12345678'
        }
        form = DepositForm(data=form_data)
        self.assertTrue(form.is_valid())
        dep = services.create_deposit(
            user=self.client_user,
            amount=form.cleaned_data['amount'],
            payment_method=form.cleaned_data['payment_method'],
            sender_number=form.cleaned_data['sender_number'],
            transaction_id=form.cleaned_data['transaction_id']
        )
        self.assertEqual(dep.status, Deposit.Status.PENDING)
        self.assertEqual(dep.transaction_id, 'BK12345678')
        self.assertEqual(dep.amount, Decimal('1500.00'))

    def test_duplicate_trxid_protection_workflow(self):
        """US-21: A previously used TrxID cannot credit SkillCoin twice."""
        dep1 = services.create_deposit(
            user=self.client_user,
            amount=Decimal('1000.00'),
            payment_method=Deposit.Method.NAGAD,
            sender_number='01811223344',
            transaction_id='NAGAD9988'
        )
        dep1 = services.approve_deposit(deposit=dep1)
        self.assertEqual(dep1.status, Deposit.Status.APPROVED)
        self.client_user.wallet.refresh_from_db()
        balance_after_first = self.client_user.wallet.available_balance
        
        # Second deposit with identical TrxID cannot be approved
        dep2 = services.create_deposit(
            user=self.client_user,
            amount=Decimal('1000.00'),
            payment_method=Deposit.Method.NAGAD,
            sender_number='01811223344',
            transaction_id='NAGAD9988'
        )
        from apps.core.exceptions import ValidationFailed
        with self.assertRaises(ValidationFailed):
            services.approve_deposit(deposit=dep2)
        
        self.client_user.wallet.refresh_from_db()
        self.assertEqual(self.client_user.wallet.available_balance, balance_after_first)
