import time
from decimal import Decimal
from selenium.webdriver.common.by import By
from django.contrib.auth import get_user_model
from Sprint_4.selenium.base import BaseSprint4SeleniumTestCase
from apps.wallets.models import Deposit

User = get_user_model()

class US21SeleniumClientDepositTest(BaseSprint4SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.client_user = User.objects.create_user(
            username='selenium_deposit_client',
            email='se_deposit@test.com',
            password=self.password,
            role='CLIENT',
            is_email_verified=True
        )

    def test_client_submits_deposit_form_in_browser(self):
        """US-21: Client can submit deposit in browser UI with amount, method and TrxID."""
        self.login_user('se_deposit@test.com', self.password)
        self.driver.get(f'{self.live_server_url}/wallet/deposit/')
        time.sleep(1)

        deposit_form = self.driver.find_element(By.CSS_SELECTOR, '.deposit-container form')
        amount_input = deposit_form.find_element(By.NAME, 'amount')
        amount_input.clear()
        amount_input.send_keys('1200')

        deposit_form.find_element(By.NAME, 'sender_number').send_keys('01700112233')
        deposit_form.find_element(By.NAME, 'transaction_id').send_keys('SE_TRX_9999')

        submit_btn = deposit_form.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        time.sleep(2)

        deposit = Deposit.objects.filter(user=self.client_user, transaction_id='SE_TRX_9999').first()
        self.assertIsNotNone(deposit)
        self.assertEqual(deposit.amount, Decimal('1200.00'))
        self.assertEqual(deposit.status, Deposit.Status.PENDING)
        self.assertEqual(deposit.amount, Decimal('1200.00'))
        self.assertEqual(deposit.status, Deposit.Status.PENDING)
