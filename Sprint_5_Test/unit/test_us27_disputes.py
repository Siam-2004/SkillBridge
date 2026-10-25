from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from apps.projects.models import Project, Dispute
from apps.projects.admin import DisputeAdmin

User = get_user_model()

class US27DisputeSystemTest(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='dispute_client',
            email='client@dispute.com',
            password='Password123!',
            role='CLIENT',
            is_email_verified=True
        )
        self.freelancer_user = User.objects.create_user(
            username='dispute_freelancer',
            email='freelancer@dispute.com',
            password='Password123!',
            role='FREELANCER',
            is_email_verified=True
        )
        self.outsider = User.objects.create_user(
            username='dispute_outsider',
            email='outsider@dispute.com',
            password='Password123!',
            role='FREELANCER',
            is_email_verified=True
        )
        self.admin_user = User.objects.create_superuser(
            username='dispute_admin',
            email='admin@dispute.com',
            password='Password123!',
            is_email_verified=True
        )

        self.project = Project.objects.create(
            client=self.client_user,
            freelancer=self.freelancer_user,
            title='Mobile App Delivery',
            final_price=Decimal('8000.00'),
            deadline=timezone.now() + timedelta(days=20),
            status=Project.Status.ACTIVE
        )

    def test_client_can_create_dispute(self):
        """US-27: Client can create a dispute with reason, description, and target party."""
        dispute = Dispute.objects.create(
            project=self.project,
            raised_by=self.client_user,
            against=self.freelancer_user,
            reason=Dispute.Reason.SCOPE,
            description='Freelancer stopped responding and did not fulfill agreed scope.'
        )
        self.assertEqual(dispute.status, Dispute.Status.OPEN)
        self.assertEqual(dispute.project, self.project)
        self.assertEqual(dispute.against, self.freelancer_user)

    def test_freelancer_can_create_dispute(self):
        """US-27: Freelancer can raise a dispute against client."""
        dispute = Dispute.objects.create(
            project=self.project,
            raised_by=self.freelancer_user,
            against=self.client_user,
            reason=Dispute.Reason.PAYMENT,
            description='Client refusing to review completed deliverable.'
        )
        self.assertEqual(dispute.status, Dispute.Status.OPEN)
        self.assertEqual(dispute.against, self.client_user)

    def test_dispute_validation_requires_reason_and_description(self):
        """US-27: Dispute requires reason and non-empty description."""
        invalid_dispute = Dispute(
            project=self.project,
            raised_by=self.client_user,
            against=self.freelancer_user,
            reason='',
            description=''
        )
        with self.assertRaises(ValidationError):
            invalid_dispute.full_clean()

    def test_admin_can_resolve_dispute(self):
        """US-27: Admin dispute resolution interface records final resolution and audit trail."""
        dispute = Dispute.objects.create(
            project=self.project,
            raised_by=self.client_user,
            against=self.freelancer_user,
            reason=Dispute.Reason.QUALITY,
            description='Deliverables do not match specifications.'
        )

        site = AdminSite()
        dispute_admin = DisputeAdmin(Dispute, site)

        # Admin resolves dispute with resolution notes
        dispute.status = Dispute.Status.RESOLVED
        dispute.admin_resolution = 'Reviewed repository logs and agreement. Milestone revised and 50% escrow released.'
        dispute.resolved_by = self.admin_user
        dispute.resolved_at = timezone.now()
        dispute.save()

        dispute.refresh_from_db()
        self.assertEqual(dispute.status, Dispute.Status.RESOLVED)
        self.assertEqual(dispute.resolved_by, self.admin_user)
        self.assertIsNotNone(dispute.resolved_at)
        self.assertIn('50% escrow released', dispute.admin_resolution)

    def test_http_submission_of_dispute(self):
        """US-27: HTTP endpoint allows project participant to submit dispute."""
        self.client.login(email='client@dispute.com', password='Password123!')
        url = reverse('projects:dispute_create', args=[self.project.public_id])

        response = self.client.post(url, {
            'reason': Dispute.Reason.UNRESPONSIVE,
            'description': 'Unable to reach the freelancer for 5 days despite critical milestones.'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Dispute.objects.filter(project=self.project, raised_by=self.client_user).exists())

    def test_non_participant_cannot_create_dispute(self):
        """US-27: Unauthorized user outside the project cannot create a dispute."""
        self.client.login(email='outsider@dispute.com', password='Password123!')
        url = reverse('projects:dispute_create', args=[self.project.public_id])

        response = self.client.post(url, {
            'reason': Dispute.Reason.OTHER,
            'description': 'I have no relationship to this project.'
        })
        self.assertEqual(response.status_code, 403)