import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conv_id = self.scope['url_route']['kwargs']['conv_id']
        self.room_group = f'chat_{self.conv_id}'
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        text = data.get('text', '').strip()
        user = self.scope['user']

        if not text or not user.is_authenticated:
            return

        message = await self.save_message(user, self.conv_id, text)

        await self.channel_layer.group_send(self.room_group, {
            'type': 'chat_message',
            'text': text,
            'sender': user.username,
            'sender_id': user.id,
            'time': message.created_at.strftime('%H:%M'),
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'text': event['text'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'time': event['time'],
        }))

    @database_sync_to_async
    def save_message(self, user, conv_id, text):
        from messaging.models import Conversation, Message
        conv = Conversation.objects.get(pk=conv_id)
        msg = Message.objects.create(conversation=conv, sender=user, text=text)
        conv.last_message = text
        conv.read_by_seller = user == conv.seller
        conv.read_by_buyer = user == conv.buyer
        conv.save()
        return msg
