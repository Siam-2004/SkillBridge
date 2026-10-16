from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.projects.models import Project, Team, TeamInvitation
from apps.projects import services
from apps.core.exceptions import ValidationFailed

User = get_user_model()

class US31TeamInvitationExpirationTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='team_owner',
            email='owner@test.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.invitee = User.objects.create_user(
            username='team_invitee',
            email='invitee@test.com',
            password='Password123!',
            role='FREELANCER'
        )
        self.client = User.objects.create_user(
            username='client_team',
            email='client_team@test.com',
            password='Password123!',
            role='CLIENT'
        )
        self.project = Project.objects.create(
            client=self.client,
            freelancer=self.owner,
            title='Expiration Project',
            final_price=1000,
            deadline=timezone.now() + timedelta(days=7)
        )
        self.team = Team.objects.create(
            project=self.project,
            name='Alpha Team',
            owner=self.owner
        )

    def test_active_invitation_within_48_hours_can_be_accepted(self):
        """US-31: Active invitation can be accepted normally."""
        inv = services.invite_to_team(self.team, self.invitee, self.owner)
        self.assertFalse(inv.is_expired)
        services.respond_to_invitation(inv, self.invitee, accept=True)
        inv.refresh_from_db()
        self.assertEqual(inv.status, TeamInvitation.Status.ACCEPTED)

    def test_expired_invitation_after_48_hours_is_rejected(self):
        """US-31: Invitations after 48 hours are expired and cannot be accepted."""
        inv = services.invite_to_team(self.team, self.invitee, self.owner)
        # Simulate 49 hours passed via queryset update
        past_time = timezone.now() - timedelta(hours=49)
        TeamInvitation.objects.filter(pk=inv.pk).update(created_at=past_time)
        inv.refresh_from_db()

        self.assertTrue(inv.is_expired)
        with self.assertRaises(ValidationFailed):
            services.respond_to_invitation(inv, self.invitee, accept=True)
        inv.refresh_from_db()
        self.assertEqual(inv.status, TeamInvitation.Status.EXPIRED)
