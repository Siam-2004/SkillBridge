from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.projects.models import Project, Team, TeamMember
from apps.tasks.models import Task
from apps.tasks import services

User = get_user_model()

class US33TeamMemberEscrowPaymentTest(TestCase):
    def setUp(self):
        self.client = User.objects.create_user(
            username='client_escrow',
            email='client_escrow@test.com',
            password='Password123!',
            role='CLIENT'
        )
        self.owner = User.objects.create_user(
            username='lead_freelancer',
            email='lead@test.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.member = User.objects.create_user(
            username='assigned_member',
            email='member@test.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.client.wallet.available_balance = Decimal('5000.00')
        self.client.wallet.escrow_balance = Decimal('1000.00')
        self.client.wallet.save()

        self.project = Project.objects.create(
            client=self.client,
            freelancer=self.owner,
            title='Team Escrow Project',
            final_price=Decimal('1000.00'),
            deadline=timezone.now() + timedelta(days=5)
        )
        self.team = Team.objects.create(
            project=self.project,
            name='Dev Team',
            owner=self.owner
        )
        TeamMember.objects.create(team=self.team, user=self.owner, role=TeamMember.Role.OWNER)
        TeamMember.objects.create(team=self.team, user=self.member, role=TeamMember.Role.MEMBER)

    def test_completing_task_pays_assigned_team_member(self):
        """US-33: Completing assigned task by leader automatically transfers allocated funds to member."""
        task = services.create_task(
            project=self.project,
            title='Build Frontend Module',
            created_by=self.owner,
            assigned_to=self.member,
            skillcoin_allocation=Decimal('350.00')
        )
        initial_member_balance = self.member.wallet.available_balance

        # Leader approves task as COMPLETED
        services.update_task_status(task=task, new_status=Task.Status.COMPLETED, actor=self.owner)

        self.member.wallet.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.assertEqual(self.member.wallet.available_balance, initial_member_balance + Decimal('350.00'))

    def test_member_cannot_self_approve_completion(self):
        """US-33: Assigned team member cannot directly mark task as COMPLETED to bypass review."""
        from apps.core.exceptions import PermissionDenied
        task = services.create_task(
            project=self.project,
            title='Backend Auth Module',
            created_by=self.owner,
            assigned_to=self.member,
            skillcoin_allocation=Decimal('400.00')
        )
        with self.assertRaises(PermissionDenied):
            services.update_task_status(task=task, new_status=Task.Status.COMPLETED, actor=self.member)

    def test_member_submit_requires_deliverable_file(self):
        """US-33: Member submitting task for review with monetary allocation must provide work files."""
        from apps.core.exceptions import ValidationFailed
        from django.core.files.uploadedfile import SimpleUploadedFile
        task = services.create_task(
            project=self.project,
            title='Design Mockups',
            created_by=self.owner,
            assigned_to=self.member,
            skillcoin_allocation=Decimal('250.00')
        )
        # Attempt to submit without uploading deliverable
        with self.assertRaises(ValidationFailed):
            services.update_task_status(task=task, new_status=Task.Status.IN_REVIEW, actor=self.member)

        # Upload a deliverable file
        dummy_file = SimpleUploadedFile("mockup.png", b"file_content", content_type="image/png")
        services.upload_task_file(task=task, uploaded_by=self.member, file=dummy_file)

        # Now submission succeeds
        services.update_task_status(task=task, new_status=Task.Status.IN_REVIEW, actor=self.member)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_REVIEW)
        self.assertIsNotNone(task.submitted_at)

    def test_auto_approval_after_48_hours(self):
        """US-33: If Leader does not review within 48 hours, task auto-approves and releases funds."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        task = services.create_task(
            project=self.project,
            title='Database Schema',
            created_by=self.owner,
            assigned_to=self.member,
            skillcoin_allocation=Decimal('300.00')
        )
        dummy_file = SimpleUploadedFile("schema.sql", b"CREATE TABLE...", content_type="text/plain")
        services.upload_task_file(task=task, uploaded_by=self.member, file=dummy_file)
        services.update_task_status(task=task, new_status=Task.Status.IN_REVIEW, actor=self.member)

        # Simulate 49 hours passed without leader action
        task.submitted_at = timezone.now() - timedelta(hours=49)
        task.save(update_fields=['submitted_at'])
        self.assertTrue(task.is_review_expired)

        initial_balance = self.member.wallet.available_balance
        services.check_and_auto_approve_task(task)

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.member.wallet.refresh_from_db()
        self.assertEqual(self.member.wallet.available_balance, initial_balance + Decimal('300.00'))
