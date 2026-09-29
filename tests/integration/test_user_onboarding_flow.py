from django.test import TestCase, Client
from unittest.mock import patch
from apps.accounts.models import User, Role, EmailVerificationToken
from apps.accounts import services as account_services

class UserOnboardingIntegrationTestCase(TestCase):
    def test_complete_client_onboarding_flow(self):
        # 1. Register a new Client with mock email
        with patch('apps.accounts.services.send_verification_email') as mock_email:
            user = account_services.register(
                email='kamrulhasansiam29@gmail.com',
                username='siam',
                password='mominrifat2211',
                role=Role.CLIENT,
                first_name='Kamrul Hasan',
                last_name='Siam'
            )
            self.assertEqual(user.email, 'kamrulhasansiam29@gmail.com')
            self.assertEqual(user.username, 'siam')
            self.assertFalse(user.is_email_verified)
            self.assertTrue(user.is_client)

        # 2. Verification token generation
        token = EmailVerificationToken.objects.create(
            user=user,
            email=user.email,
            expires_at=user.date_joined + account_services.timedelta(hours=24)
        )

        # 3. Verify email using token
        verified_user = account_services.verify_email(token=token.token)
        self.assertTrue(verified_user.is_email_verified)
        self.assertTrue(verified_user.can_transact)

        # 4. Check client profile & wallet were automatically initialized
        self.assertTrue(hasattr(verified_user, 'client_profile'))
        self.assertTrue(hasattr(verified_user, 'wallet'))
        self.assertEqual(verified_user.wallet.available_balance, 0)

        # 5. Authenticate and test login with Django Test Client
        client = Client()
        login_success = client.login(username='kamrulhasansiam29@gmail.com', password='mominrifat2211')
        self.assertTrue(login_success)

    def test_complete_freelancer_onboarding_flow(self):
        # 1. Register a new Freelancer
        with patch('apps.accounts.services.send_verification_email'):
            user = account_services.register(
                email='mominrifat8@gmail.com',
                username='rifat',
                password='mominrifat2211',
                role=Role.FREELANCER,
                first_name='Momin',
                last_name='Rifat'
            )
            self.assertTrue(user.is_freelancer)
            self.assertEqual(user.username, 'rifat')
            self.assertFalse(user.is_email_verified)

        # 2. Verify via 6-digit OTP code
        token = EmailVerificationToken.objects.create(
            user=user,
            email=user.email,
            code='654321',
            expires_at=user.date_joined + account_services.timedelta(hours=24)
        )
        verified_user = account_services.verify_code(code='654321', user=user)
        self.assertTrue(verified_user.is_email_verified)
        self.assertTrue(hasattr(verified_user, 'freelancer_profile'))
