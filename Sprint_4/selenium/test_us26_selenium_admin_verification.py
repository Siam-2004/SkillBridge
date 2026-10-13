import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from django.contrib.auth import get_user_model
from Sprint_4.selenium.base import BaseSprint4SeleniumTestCase
from apps.wallets.models import Deposit

User = get_user_model()

class US26SeleniumAdminVerificationTest(BaseSprint4SeleniumTestCase):
    def setUp(self):
        self.password = 'Admin'
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='adminrifat@gmail.com',
            password=self.password
        )
        self.client_user = User.objects.create_user(
            username='siam',
            email='siam@gmail.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )
        self.client_user.wallet.available_balance = Decimal('1000.00')
        self.client_user.wallet.save()

        self.deposit = Deposit.objects.create(
            user=self.client_user,
            amount=Decimal('2000.00'),
            payment_method=Deposit.Method.BKASH,
            transaction_id='SE_ADMIN_TRX_8888',
            status=Deposit.Status.PENDING
        )

    def test_admin_approves_pending_deposit_in_admin_panel(self):
        """US-26: Admin views pending deposit in Admin interface, approves it and credits user wallet."""
        initial_balance = self.client_user.wallet.available_balance

        # 1. Admin signs in
        self.login_user('adminrifat@gmail.com', self.password)

        # 2. Admin navigates to the Deposits changelist view
        self.driver.get(f'{self.live_server_url}/admin/wallets/deposit/')
        time.sleep(1)

        # Verify pending deposit is visible on screen
        self.assertIn('SE_ADMIN_TRX_8888', self.driver.page_source)

        # 3. Select the deposit row checkbox
        checkbox = self.driver.find_element(By.CSS_SELECTOR, f'input[name="_selected_action"][value="{self.deposit.pk}"]')
        checkbox.click()

        # 4. Choose 'approve_deposits' action
        action_dropdown = self.driver.find_element(By.NAME, 'action')
        Select(action_dropdown).select_by_value('approve_deposits')

        # 5. Submit action
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"][name="index"]')
        submit_btn.click()
        time.sleep(1.5)

        # 6. Verify deposit status transitioned to APPROVED in database
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, Deposit.Status.APPROVED)
        self.assertIsNotNone(self.deposit.approved_at)

        # 7. Verify user wallet is credited with exact amount
        self.client_user.wallet.refresh_from_db()
        self.assertEqual(self.client_user.wallet.available_balance, initial_balance + Decimal('2000.00'))
