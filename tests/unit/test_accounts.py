from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role, EmailVerificationToken
class UserModelUnitTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',
            username='siam',
            password='mominrifat2211',
            role=Role.CLIENT,
            first_name='Kamrul Hasan',
            last_name='Siam'
        )
        self.freelancer_user = User.objects.create_user(
            email='mominrifat8@gmail.com',
            username='rifat',
            password='mominrifat2211',
            role=Role.FREELANCER,
            first_name='Momin',
            last_name='Rifat'
        )

    def test_user_creation_and_roles(self):
        self.assertEqual(self.client_user.email, 'kamrulhasansiam29@gmail.com')
        self.assertEqual(self.client_user.username, 'siam')
        self.assertTrue(self.client_user.is_client)
        self.assertFalse(self.client_user.is_freelancer)
        self.assertEqual(self.freelancer_user.email, 'mominrifat8@gmail.com')
        self.assertEqual(self.freelancer_user.username, 'rifat')
        self.assertTrue(self.freelancer_user.is_freelancer)
        self.assertFalse(self.freelancer_user.is_client)

    def test_user_full_name_and_initials(self):
        self.assertEqual(self.client_user.full_name, 'Kamrul Hasan Siam')
        self.assertEqual(self.client_user.initials, 'KS')
        self.assertEqual(self.freelancer_user.full_name, 'Momin Rifat')
        self.assertEqual(self.freelancer_user.initials, 'MR')

    def test_superuser_creation(self):
        admin = User.objects.create_superuser(
            email='sabbir@skillbridge.test',
            username='sabbir',
            password='mominrifat2211',
            first_name='Sabbir',
            last_name='Hossain'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_platform_admin)
        self.assertTrue(admin.is_email_verified)

    def test_email_normalization(self):
        user = User.objects.create_user(
            email='Rahat.Mehrab@SkillBridge.TEST',
            username='rahat',
            password='mominrifat2211',
            first_name='Mehrab Hossen',
            last_name='Rahat'
        )
        self.assertEqual(user.email, 'rahat.mehrab@skillbridge.test')
        self.assertEqual(user.full_name, 'Mehrab Hossen Rahat')

    def test_can_transact_requires_verification(self):
        self.assertFalse(self.client_user.can_transact)
        self.client_user.is_email_verified = True
        self.client_user.save()
        self.assertTrue(self.client_user.can_transact)

    def test_user_wallet_and_profile_bootstrapped_via_signal(self):
        self.assertTrue(hasattr(self.client_user, 'wallet'))
        self.assertTrue(hasattr(self.client_user, 'client_profile'))
        self.assertTrue(hasattr(self.freelancer_user, 'wallet'))
        self.assertTrue(hasattr(self.freelancer_user, 'freelancer_profile'))

    def test_email_verification_token(self):
        token = EmailVerificationToken.objects.create(
            user=self.client_user,
            email=self.client_user.email,
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        self.assertTrue(token.is_valid)
        self.assertEqual(len(token.code), 6)

