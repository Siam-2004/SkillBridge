from django.test import TestCase
from apps.accounts.models import User, Role
from apps.messaging.models import Conversation, ConversationParticipant, Message
class MessagingUnitTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='kamrulhasansiam29@gmail.com',username='siam',password='mominrifat2211',role=Role.CLIENT,first_name='Kamrul Hasan',last_name='Siam'
        )
        self.user2 = User.objects.create_user(
            email='mominrifat8@gmail.com',username='rifat',password='mominrifat2211',role=Role.FREELANCER,first_name='Momin',last_name='Rifat'
        )
    def test_conversation_and_message_creation(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Kind.JOB,subject='Discussion regarding project scope',initiator=self.user1
        )
        ConversationParticipant.objects.create(
            conversation=conversation,user=self.user1,role=ConversationParticipant.Role.CLIENT
        )
        ConversationParticipant.objects.create(
            conversation=conversation,user=self.user2,role=ConversationParticipant.Role.FREELANCER
        )
        message = Message.objects.create(
            conversation=conversation,sender=self.user1,content='Hi! I am Sabbir. When can you start the work?'
        )
        self.assertEqual(conversation.participants.count(), 2)
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(message.content, 'Hi! When can you start the work?')
        self.assertTrue(conversation.is_writable)
