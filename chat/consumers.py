
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Conversation, Message
from accounts.permissions import is_user_blocked


MAX_MESSAGE_LENGTH = 5000
MAX_FRAME_LENGTH = 65536
MAX_SIGNAL_PAYLOAD_LENGTH = 60000


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.user = self.scope['user']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.in_call = False

        if not self.user.is_authenticated:
            await self.close()
            return

        if not await self.has_access():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            if getattr(self, 'in_call', False):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'webrtc_signal',
                        'event': 'call_end',
                        'sender_username': self.user.username,
                        'call_type': 'video',
                        'payload': {},
                    }
                )

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None:
            await self.close(code=1003)
            return

        if not text_data or len(text_data) > MAX_FRAME_LENGTH:
            await self.close(code=1009)
            return

        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send_json({
                'type': 'error',
                'message': 'Invalid JSON.'
            })
            return

        if not isinstance(data, dict):
            await self.send_json({
                'type': 'error',
                'message': 'Invalid message format.'
            })
            return

        if not await self.has_access():
            await self.close(code=1008)
            return

        message_type = data.get('type')

        if message_type == 'chat_message':
            await self.handle_chat_message(data)

        elif message_type == 'typing':
            await self.handle_typing(data)

        elif data.get('action') in (
            'call_offer',
            'call_answer',
            'ice_candidate',
            'call_reject',
            'call_end'
        ) or message_type in (
            'call_offer',
            'call_answer',
            'ice_candidate',
            'call_reject',
            'call_end'
        ):
            await self.handle_webrtc_signal(data)

    async def handle_chat_message(self, data):
        content = data.get('message', '')

        if not isinstance(content, str):
            return

        content = content.strip()

        if not content or len(content) > MAX_MESSAGE_LENGTH:
            return

        message = await self.save_message(content)

        if message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': content,
                    'sender': self.user.username,
                    'message_id': message.id,
                }
            )

    async def handle_typing(self, data):
        is_typing = data.get('is_typing')

        if not isinstance(is_typing, bool):
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing',
                'username': self.user.username,
                'is_typing': is_typing,
            }
        )

    async def handle_webrtc_signal(self, data):
        action = data.get('action') or data.get('type')
        call_type = data.get('call_type', 'video')
        payload = data.get('payload', {})

        allowed_actions = (
            'call_offer',
            'call_answer',
            'ice_candidate',
            'call_reject',
            'call_end'
        )

        if action not in allowed_actions:
            return

        if call_type not in ('audio', 'video'):
            return

        if not isinstance(payload, dict):
            return

        try:
            serialized_payload = json.dumps(payload)
        except (TypeError, ValueError):
            return

        if len(serialized_payload) > MAX_SIGNAL_PAYLOAD_LENGTH:
            return

        if action in ('call_offer', 'call_answer'):
            sdp = payload.get('sdp')

            if not isinstance(sdp, str):
                return

            if not sdp or len(sdp) > MAX_SIGNAL_PAYLOAD_LENGTH:
                return

        if action == 'ice_candidate':
            candidate = payload.get('candidate')

            if candidate is not None and not isinstance(candidate, (str, dict)):
                return

        if action == 'call_offer':
            self.in_call = True

        elif action in ('call_reject', 'call_end'):
            self.in_call = False

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_signal',
                'event': action,
                'sender_username': self.user.username,
                'call_type': call_type,
                'payload': payload,
            }
        )

    async def chat_message(self, event):
        if not await self.has_access():
            await self.close(code=1008)
            return

        await self.send_json({
            'type': 'chat_message',
            'message': event['message'],
            'sender': event['sender'],
            'message_id': event.get('message_id'),
        })

    async def typing(self, event):
        if not await self.has_access():
            await self.close(code=1008)
            return

        await self.send_json({
            'type': 'typing',
            'username': event['username'],
            'is_typing': event['is_typing'],
        })

    async def webrtc_signal(self, event):
        if not await self.has_access():
            await self.close(code=1008)
            return

        await self.send_json({
            'type': 'webrtc_signal',
            'event': event['event'],
            'sender_username': event['sender_username'],
            'call_type': event['call_type'],
            'payload': event.get('payload', {}),
        })

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content))

    @database_sync_to_async
    def has_access(self):
        try:
            conversation = Conversation.objects.get(
                id=self.conversation_id
            )

            if not conversation.participants.filter(
                id=self.user.id
            ).exists():
                return False

            other_user = conversation.get_other_participant(self.user)

            if other_user and is_user_blocked(self.user, other_user):
                return False

            return True

        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        try:
            conversation = Conversation.objects.get(
                id=self.conversation_id
            )

            if not conversation.participants.filter(
                id=self.user.id
            ).exists():
                return None

            other_user = conversation.get_other_participant(self.user)

            if other_user and is_user_blocked(self.user, other_user):
                return None

            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content
            )

            conversation.save()

            return message

        except Conversation.DoesNotExist:
            return None
