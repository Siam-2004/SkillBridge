from django.test import TestCase
from apps.accounts.models import User, Role
from apps.profiles.models import FreelancerProfile
from apps.portfolios.models import Portfolio
class PortfolioUnitTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='mominrifat8@gmail.com',
            username='rifat',
            password='mominrifat2211',
            role=Role.FREELANCER,
            first_name='Momin',
            last_name='Rifat'
        )
        self.profile = FreelancerProfile.objects.get(user=self.user)

    def test_portfolio_item_creation(self):
        item = Portfolio.objects.create(
            freelancer=self.profile,
            title='E-commerce Backend in Django',
            description='Complete microservices backend with payment gateways.',
            demo_url='https://example.com/demo',
            technologies='Django, Celery, Redis, PostgreSQL'
        )
        self.assertEqual(item.title, 'E-commerce Backend in Django')
        self.assertEqual(item.slug, 'e-commerce-backend-in-django')
        self.assertTrue(item.is_public)
        self.assertEqual(item.freelancer, self.profile)