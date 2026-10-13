import time

from decimal import Decimal
from selenium.webdriver.common.by import By
from django.contrib.auth import get_user_model
from Sprint_4.selenium.base import BaseSprint4SeleniumTestCase
from apps.wallets.models import Withdrawal

User = get_user_model()

class US24SeleniumWithdrawalTest(BaseSprint4SeleniumTestCase):
    def setUp(self):
        self.password = 'Pass123456!'
        self.freelancer = User.objects.create_user(
            username='selenium_wdr_freelancer',
            email='se_wdr@test.com',
            password=self.password,
            role='FREELANCER',
            is_email_verified=True
        )
        self.freelancer.wallet.available_balance = Decimal('3000.00')
        self.freelancer.wallet.reserved_balance = Decimal('0.00')
        self.freelancer.wallet.save()

    def test_freelancer_requests_withdrawal_in_browser(self):
        """US-24: Freelancer submits withdrawal in browser UI and reserves funds."""
        self.login_user('se_wdr@test.com', self.password)
        self.driver.get(f'{self.live_server_url}/wallet/withdraw/')
        time.sleep(1)

        withdraw_form = self.driver.find_element(By.CSS_SELECTOR, '.withdraw-container form')
        amount_input = withdraw_form.find_element(By.NAME, 'amount')
        amount_input.clear()
        amount_input.send_keys('1500')

        withdraw_form.find_element(By.NAME, 'account_number').send_keys('01899001122')
        withdraw_form.find_element(By.NAME, 'account_name').send_keys('Freelancer Name')

        submit_btn = withdraw_form.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_btn.click()
        time.sleep(2)

        wdr = Withdrawal.objects.filter(user=self.freelancer, amount=Decimal('1500.00')).first()
        self.assertIsNotNone(wdr)
        self.assertEqual(wdr.status, Withdrawal.Status.PENDING)
        self.freelancer.wallet.refresh_from_db()
        self.assertEqual(self.freelancer.wallet.reserved_balance, Decimal('1500.00'))
        self.assertEqual(self.freelancer.wallet.available_balance, Decimal('1500.00'))