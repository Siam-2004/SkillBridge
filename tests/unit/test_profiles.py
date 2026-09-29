from django.test import TestCase
from apps.accounts.models import User, Role
from apps.profiles.models import Category, Skill, ClientProfile, FreelancerProfile

class ProfileUnitTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',
            username='siam',
            password='mominrifat2211',
            role=Role.CLIENT,
            first_name='Kamrul Hasan',
            last_name='Siam'
        )
        self.freelancer = User.objects.create_user(
            email='mominrifat8@gmail.com',
            username='rifat',
            password='mominrifat2211',
            role=Role.FREELANCER,
            first_name='Momin',
            last_name='Rifat'
        )

    def test_category_and_skill_slugification(self):
        cat = Category.objects.create(name='Mobile App Development')
        self.assertEqual(cat.slug, 'mobile-app-development')
        skill = Skill.objects.create(name='React Native', category=cat)
        self.assertEqual(skill.slug, 'react-native')
        self.assertEqual(skill.category, cat)

    def test_client_and_freelancer_profiles_exist(self):
        client_prof = ClientProfile.objects.get(user=self.client_user)
        self.assertEqual(client_prof.user, self.client_user)

        freelancer_prof = FreelancerProfile.objects.get(user=self.freelancer)
        self.assertEqual(freelancer_prof.user, self.freelancer)
        self.assertFalse(self.freelancer.is_email_verified)
