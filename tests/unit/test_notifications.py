from django.test import TestCase
from apps.accounts.models import User, Role
from apps.notifications.models import Notification, NotificationType
from apps.notifications import services

class NotificationUnitTestCase(TestCase):
    def setUp(self):
        self.recipient = User.objects.create_user(
            email='mominrifat8@gmail.com',username='rifat',password='mominrifat2211',role=Role.FREELANCER,first_name='Momin',last_name='Rifat'
        )
        self.actor = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',username='siam',password='mominrifat2211',role=Role.CLIENT,first_name='Kamrul Hasan',last_name='Siam'
        )

    def test_create_notification(self):
        note = services.notify(
            recipient=self.recipient,kind=NotificationType.NEW_MESSAGE,title='You have a new message',message='Hello there!',actor=self.actor,email=False
        )
        self.assertIsNotNone(note)
        self.assertEqual(note.recipient, self.recipient)
        self.assertEqual(note.actor, self.actor)
        self.assertIsNone(note.read_at)
        self.assertEqual(services.unread_count(self.recipient), 1)

    def test_mark_notification_as_read(self):
        note = services.notify(
            recipient=self.recipient,kind=NotificationType.PROPOSAL_ACCEPTED,title='Proposal accepted',message='Congratulations!',actor=self.actor,email=False
        )
        self.assertEqual(services.unread_count(self.recipient), 1)
        count = services.mark_read(self.recipient, public_ids=[note.public_id])
        self.assertEqual(count, 1)
        self.assertEqual(services.unread_count(self.recipient), 0)

    def test_cannot_notify_self(self):
        # A user notifying themselves should return None
        note = services.notify(
            recipient=self.actor,kind=NotificationType.ACCOUNT_NOTICE,title='Self note',actor=self.actor,email=False
        )
        self.assertIsNone(note)
