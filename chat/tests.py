
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from chat.models import Conversation, Message, MessageReaction
from accounts.models import Block


class ChatFunctionalityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = User.objects.create_user(
            username='alice',
            password='Password123!',
            email='alice@example.com'
        )
        self.bob = User.objects.create_user(
            username='bob',
            password='Password123!',
            email='bob@example.com'
        )
        self.charlie = User.objects.create_user(
            username='charlie',
            password='Password123!',
            email='charlie@example.com'
        )

    def test_inbox_view(self):
        """Authenticated user can view their conversation inbox."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )
        Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="Hello Alice!"
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )
        res = self.client.get(reverse('chat:inbox'))

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'bob')

    def test_start_conversation_get_does_not_mutate_db(self):
        """Visiting the compose page via GET never creates conversation records."""
        self.client.login(
            username='alice',
            password='Password123!'
        )
        self.assertEqual(Conversation.objects.count(), 0)

        res = self.client.get(
            reverse('chat:start_conversation', args=['bob'])
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(Conversation.objects.count(), 0)

    def test_start_conversation_post_creates_conversation(self):
        """Posting the initial message creates the 1-on-1 thread and first message."""
        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.post(
            reverse('chat:start_conversation', args=['bob']),
            {'content': 'First message to start the thread.'}
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 1)

        conv = Conversation.objects.first()

        self.assertEqual(conv.participants.count(), 2)
        self.assertTrue(
            conv.participants.filter(id=self.alice.id).exists()
        )
        self.assertTrue(
            conv.participants.filter(id=self.bob.id).exists()
        )
        self.assertEqual(conv.messages.count(), 1)
        self.assertEqual(
            conv.messages.first().content,
            'First message to start the thread.'
        )

    def test_start_conversation_duplicate_prevention(self):
        """Attempting to start conversation with existing partner redirects to existing thread."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.get(
            reverse('chat:start_conversation', args=['bob'])
        )

        self.assertEqual(res.status_code, 302)
        self.assertEqual(
            res.url,
            reverse('chat:conversation', args=[conv.id])
        )
        self.assertEqual(Conversation.objects.count(), 1)

    def test_message_sending_text(self):
        """User can send a text message in an existing conversation."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.post(
            reverse('chat:conversation', args=[conv.id]),
            {'content': 'How is NIVO going?'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(conv.messages.count(), 1)

        msg = conv.messages.first()

        self.assertEqual(msg.content, 'How is NIVO going?')
        self.assertEqual(msg.sender, self.alice)

    def test_message_sending_voice_audio(self):
        """User can upload genuine voice recordings with duration."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        audio_data = b'\x1a\x45\xdf\xa3' + b'\x00' * 64
        audio_file = SimpleUploadedFile(
            "recording.webm",
            audio_data,
            content_type="audio/webm"
        )

        res = self.client.post(
            reverse('chat:conversation', args=[conv.id]),
            {
                'audio_file': audio_file,
                'audio_duration': 14,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(conv.messages.count(), 1)

        msg = conv.messages.first()

        self.assertTrue(bool(msg.audio_file))
        self.assertEqual(msg.audio_duration, 14)

    def test_message_sending_invalid_audio_rejected(self):
        """Fake or invalid audio formats are rejected with a form error."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        corrupt_audio = SimpleUploadedFile(
            "bad.webm",
            b"plain_text_not_audio",
            content_type="audio/webm"
        )

        res = self.client.post(
            reverse('chat:conversation', args=[conv.id]),
            {'audio_file': corrupt_audio},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(conv.messages.count(), 0)

    def test_message_reply_to(self):
        """Messages can thread as replies to earlier messages."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        original = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="Original question"
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.post(
            reverse('chat:conversation', args=[conv.id]),
            {
                'content': 'This is my reply.',
                'reply_to': original.id,
            }
        )

        self.assertEqual(res.status_code, 302)

        reply = conv.messages.get(content='This is my reply.')
        self.assertEqual(reply.reply_to, original)

    def test_conversation_view_is_read_only_on_get(self):
        """Viewing a conversation thread on GET does not mutate is_read status."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        msg = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="Unread message",
            is_read=False
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.get(
            reverse('chat:conversation', args=[conv.id])
        )

        self.assertEqual(res.status_code, 200)

        msg.refresh_from_db()
        self.assertFalse(msg.is_read)

    def test_mark_conversation_read_view(self):
        """Marking conversation read requires POST."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        msg = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="Unread message",
            is_read=False
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        get_res = self.client.get(
            reverse('chat:mark_read', args=[conv.id])
        )

        self.assertEqual(get_res.status_code, 403)

        msg.refresh_from_db()
        self.assertFalse(msg.is_read)

        post_res = self.client.post(
            reverse('chat:mark_read', args=[conv.id])
        )

        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()['updated_count'], 1)

        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_poll_messages_view(self):
        """Polling returns new messages strictly as a read-only query."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        m1 = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="First message"
        )
        m2 = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="Second message",
            is_read=False
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.get(
            reverse('chat:poll_messages', args=[conv.id])
            + f'?last_id={m1.id}'
        )

        self.assertEqual(res.status_code, 200)

        msgs = res.json()['messages']

        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]['id'], m2.id)

        m2.refresh_from_db()
        self.assertFalse(m2.is_read)

    def test_message_react_view(self):
        """Participants can toggle emoji reactions on messages."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        msg = Message.objects.create(
            conversation=conv,
            sender=self.bob,
            content="React to this!"
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res_add = self.client.post(
            reverse('chat:react_message', args=[msg.id]),
            {'emoji': '🔥'}
        )

        self.assertEqual(res_add.status_code, 200)
        self.assertTrue(res_add.json()['is_reacted'])

        self.assertTrue(
            MessageReaction.objects.filter(
                message=msg,
                user=self.alice,
                emoji='🔥'
            ).exists()
        )

        res_del = self.client.post(
            reverse('chat:react_message', args=[msg.id]),
            {'emoji': '🔥'}
        )

        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(res_del.json()['is_reacted'])

        self.assertFalse(
            MessageReaction.objects.filter(
                message=msg,
                user=self.alice,
                emoji='🔥'
            ).exists()
        )

    def test_delete_message_authorization(self):
        """Sender can delete their own message; other users get 403 Forbidden."""
        conv, _ = Conversation.get_or_create_direct(
            self.alice, self.bob
        )

        msg = Message.objects.create(
            conversation=conv,
            sender=self.alice,
            content="Delete me"
        )

        self.client.login(
            username='bob',
            password='Password123!'
        )

        res_forbidden = self.client.post(
            reverse('chat:delete_message', args=[msg.id])
        )

        self.assertEqual(res_forbidden.status_code, 403)
        self.assertTrue(Message.objects.filter(id=msg.id).exists())

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res_ok = self.client.post(
            reverse('chat:delete_message', args=[msg.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(res_ok.status_code, 200)
        self.assertFalse(Message.objects.filter(id=msg.id).exists())

    def test_blocked_user_cannot_be_messaged(self):
        """Messaging blocked users is disallowed."""
        Block.objects.create(
            blocker=self.alice,
            blocked=self.bob
        )

        self.client.login(
            username='alice',
            password='Password123!'
        )

        res = self.client.get(
            reverse('chat:start_conversation', args=['bob'])
        )

        self.assertEqual(res.status_code, 302)


from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from nivo_project.asgi import application


class ChatWebSocketAndWebRTCTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='ws_user1',
            password='Password123!'
        )
        self.user2 = User.objects.create_user(
            username='ws_user2',
            password='Password123!'
        )
        self.intruder = User.objects.create_user(
            username='ws_intruder',
            password='Password123!'
        )

        self.conv, _ = Conversation.get_or_create_direct(
            self.user1, self.user2
        )

    def create_communicator(self, user=None):
        """Create a WebSocket communicator with an allowed test Origin."""
        comm = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.conv.id}/',
            headers=[
                (b'origin', b'http://testserver')
            ]
        )

        if user is not None:
            comm.scope['user'] = user

        return comm

    def test_ws_unauthenticated_connection_rejected(self):
        """Unauthenticated WebSocket connections are rejected."""
        async def _test():
            comm = self.create_communicator()

            connected, _ = await comm.connect()

            self.assertFalse(connected)
            await comm.disconnect()

        async_to_sync(_test)()

    def test_ws_non_participant_connection_rejected(self):
        """Authenticated user who is not a participant is rejected."""
        async def _test():
            comm = self.create_communicator(self.intruder)

            connected, _ = await comm.connect()

            self.assertFalse(connected)
            await comm.disconnect()

        async_to_sync(_test)()

    def test_ws_authenticated_participant_connected(self):
        """Authenticated conversation participant successfully connects."""
        async def _test():
            comm = self.create_communicator(self.user1)

            connected, _ = await comm.connect()

            self.assertTrue(connected)
            await comm.disconnect()

        async_to_sync(_test)()

    def test_ws_webrtc_signaling_relay(self):
        """WebRTC call offer signal is relayed to other participants."""
        async def _test():
            comm1 = self.create_communicator(self.user1)
            connected1, _ = await comm1.connect()

            self.assertTrue(connected1)

            comm2 = self.create_communicator(self.user2)
            connected2, _ = await comm2.connect()

            self.assertTrue(connected2)

            await comm1.send_json_to({
                'action': 'call_offer',
                'call_type': 'video',
                'payload': {
                    'sdp': 'v=0\r\no=alice...'
                }
            })

            response = await comm2.receive_json_from()

            self.assertEqual(response['type'], 'webrtc_signal')
            self.assertEqual(response['event'], 'call_offer')
            self.assertEqual(response['call_type'], 'video')
            self.assertEqual(
                response['sender_username'],
                'ws_user1'
            )

            await comm1.disconnect()
            await comm2.disconnect()

        async_to_sync(_test)()
