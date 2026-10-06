from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User, Role
from apps.marketplace.models import Job
from apps.profiles.models import Category
from apps.agreements.models import Agreement

class AgreementUnitTestCase(TestCase):
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
        self.category = Category.objects.create(name='Writing', slug='writing')
        self.job = Job.objects.create(
            client=self.client_user,
            title='Dajngo Project Documentation',
            category=self.category,
            description='1500 words article.',
            budget=Decimal('200.00'),
            deadline=timezone.now() + timezone.timedelta(days=7),
            status=Job.Status.OPEN,
            budget_reserved_at=timezone.now()
        )

    def test_agreement_creation(self):
        agreement = Agreement.objects.create(
            job=self.job,
            client=self.client_user,
            freelancer=self.freelancer,
            amount=Decimal('200.00'),
            deadline=timezone.now() + timezone.timedelta(days=7),
            deliverables='1500 words markdown document',
            status=Agreement.Status.ACTIVE
        )
        self.assertEqual(agreement.amount, Decimal('200.00'))
        self.assertEqual(agreement.status, Agreement.Status.ACTIVE)
        self.assertFalse(agreement.is_completed)
        self.assertFalse(agreement.has_submitted_work)

    def test_agreement_submission_and_completion(self):
        agreement = Agreement.objects.create(
            job=self.job,
            client=self.client_user,
            freelancer=self.freelancer,
            amount=Decimal('200.00'),
            deadline=timezone.now() + timezone.timedelta(days=7),
            deliverables='Deliverable item',
            status=Agreement.Status.ACTIVE
        )
        agreement.work_submission = 'Here is the completed draft.'
        agreement.submission_link = 'https://github.com/example/article'
        agreement.submitted_at = timezone.now()
        agreement.save()
        self.assertTrue(agreement.has_submitted_work)

        agreement.status = Agreement.Status.COMPLETED
        agreement.completed_at = timezone.now()
        agreement.client_feedback = 'Excellent work!'
        agreement.save()
        self.assertTrue(agreement.is_completed)
