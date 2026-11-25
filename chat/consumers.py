
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User

from .models import Conversation, Message
from accounts.permissions import is_user_blocked


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer handling real-time chat messages, typing events,
    and WebRTC peer-to-peer audio/video call signaling.
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.in_call = False

        # Verify participant status and block restrictions.
        has_access = await self.check_access(
            self.user.id,
            self.conversation_id
        )

        if not has_access:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if not hasattr(self, 'room_group_name'):
            return

        # Notify others only if this connection was actually in a call.
        if getattr(self, 'in_call', False):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_event',
                    'event': 'call_end',
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                }
            )

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(data, dict):
            return

        # Recheck permissions on every incoming WebSocket event.
        has_access = await self.check_access(
            self.user.id,
            self.conversation_id
        )

        if not has_access:
            self.in_call = False
            await self.close(code=4403)
            return

        action = data.get('action')

        # 1. Real-time typing indicators
        if action == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_typing',
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'is_typing': bool(data.get('is_typing', True)),
                }
            )

        # 2. Real-time text message broadcast
        elif action == 'chat_message':
            content = data.get('content')

            if isinstance(content, str):
                content = content.strip()

                if content:
                    msg_data = await self.save_message(
                        self.user.id,
                        self.conversation_id,
                        content
                    )

                    if msg_data is None:
                        self.in_call = False
                        await self.close(code=4403)
                        return

                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message_broadcast',
                            'message': msg_data,
                        }
                    )

        # 3. WebRTC Calling Signaling
        elif action in (
            'call_offer',
            'call_answer',
            'ice_candidate',
            'call_reject',
            'call_end'
        ):
            if action in ('call_offer', 'call_answer'):
                self.in_call = True
            elif action in ('call_reject', 'call_end'):
                self.in_call = False

            payload = data.get('payload', {})

            if not isinstance(payload, dict):
                payload = {}

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_event',
                    'event': action,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'payload': payload,
                    'call_type': data.get('call_type', 'audio'),
                }
            )

    # Handlers for group broadcasts

    async def chat_message_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
        }))

    async def chat_typing(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'is_typing': event['is_typing'],
            }))

    async def webrtc_event(self, event):
        call_event = event.get('event')

        # Keep call state synchronized for both participants.
        if call_event in ('call_offer', 'call_answer'):
            self.in_call = True
        elif call_event in ('call_reject', 'call_end'):
            self.in_call = False

        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'webrtc_signal',
                'event': call_event,
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'payload': event.get('payload', {}),
                'call_type': event.get('call_type', 'audio'),
            }))

    def _check_access_sync(self, user_id, conversation_id):
        """
        Verify that the user belongs to the conversation
        and neither participant has blocked the other.
        """
        try:
            conversation = Conversation.objects.prefetch_related(
                'participants'
            ).get(id=conversation_id)

            user = User.objects.get(id=user_id)

        except (Conversation.DoesNotExist, User.DoesNotExist):
            return False

        if not conversation.participants.filter(id=user_id).exists():
            return False

        other_user = conversation.get_other_participant(user)

        if other_user and is_user_blocked(user, other_user):
            return False

        return True

    @database_sync_to_async
    def check_access(self, user_id, conversation_id):
        return self._check_access_sync(user_id, conversation_id)

    @database_sync_to_async
    def save_message(self, user_id, conversation_id, content):
        # Recheck permissions immediately before saving.
        if not self._check_access_sync(user_id, conversation_id):
            return None

        conversation = Conversation.objects.get(id=conversation_id)
        sender = User.objects.get(id=user_id)

        msg = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content
        )

        conversation.save()

        return {
            'id': msg.id,
            'sender_id': sender.id,
            'sender_username': sender.username,
            'content': msg.content,
            'audio_duration': msg.audio_duration,
            'created_at': msg.created_at.strftime('%H:%M'),
        }
