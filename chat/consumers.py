import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer, AsyncWebsocketConsumer
from django.contrib.auth.models import User
from .models import Message
from asgiref.sync import sync_to_async
from django.db import models
from django.db.models import Q
from datetime import datetime, date
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from collections import defaultdict
from channels.layers import get_channel_layer
from django.contrib.auth.models import User



online_users = {}
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name
        self.user = self.scope['user']
        self.notification_group_name = f"notification_{self.user.username}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.channel_layer.group_add( # Добавляем в группу уведомлений
            self.notification_group_name,
            self.channel_name
        )

        await self.accept()  # Сначала принимаем соединение

        start_date_str = self.scope['query_string'].decode().split('&start_date=')[1].split('&')[0] if 'start_date=' in self.scope['query_string'].decode() else None
        end_date_str = self.scope['query_string'].decode().split('&end_date=')[1].split('&')[0] if 'end_date=' in self.scope['query_string'].decode() else None

        # Get message history
        message_history = await self.get_message_history(start_date_str, end_date_str)

        await self.mark_messages_as_read(self.scope['user'].username)

        # Send message history
        await self.send(text_data=json.dumps({
            'type': 'message_history',
            'messages': message_history
        }, cls=DjangoJSONEncoder))

        # Добавляем пользователя в online_users при подключении
        online_users[self.user.username] = {self.channel_name}

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        await self.channel_layer.group_discard( # Удаляем из группы уведомлений
            self.notification_group_name,
            self.channel_name
        )

        # Удаляем пользователя из online_users при отключении
        if self.user.username in online_users:
            online_users[self.user.username].remove(self.channel_name)
            if not online_users[self.user.username]:
                del online_users[self.user.username]

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            sender_username = self.scope['user'].username # Использовать имя пользователя из scope
            recipient_username = self.room_name.replace(sender_username, '').replace('_','')

            

            # Проверяем, есть ли recipient_username в online_users
            if recipient_username not in online_users:
                await self.send_notification(recipient_username, message)
            else:
                print(f"Recipient {recipient_username} is online. Not sending notification.")

            # Save the message to the database
            timestamp = await self.save_message(sender_username, self.room_name, message, None, None)

            # Send the message to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender': sender_username,
                    'timestamp': timestamp.isoformat(),
                    'start_date': None,
                    'end_date': None,
                }
            )

        except Exception as e:
            print(f"Error in receive: {e}")


    async def chat_message(self, event):
        message = event['message']
        sender = event['sender']
        timestamp = event['timestamp']
        start_date = event.get('start_date')
        end_date = event.get('end_date')

        
        
        formatted_timestamp = timezone.datetime.fromisoformat(timestamp).strftime('%H:%M %d.%m.%Y')

        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': message,
            'sender': sender,
            'timestamp': formatted_timestamp,
            'start_date': start_date,
            'end_date': end_date,
        }, cls=DjangoJSONEncoder))

    async def send_notification(self, recipient_username, message):
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"notification_{recipient_username}",
            {
                'type': 'notify',
                'message': message,
            }
        )

    async def notify(self, event):
        message = event['message']

        # Send the message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': message,
        }))


    @sync_to_async
    def save_message(self, sender_username, room_name, message, start_date_str, end_date_str):
        user1, user2 = room_name.split("_")
        sender = User.objects.get(username=sender_username)
        if sender_username == user1:
            recipient = User.objects.get(username=user2)
        else:
            recipient = User.objects.get(username=user1)

        start_date = None
        end_date = None

        if start_date_str:
            start_date = timezone.datetime.fromisoformat(start_date_str)
        if end_date_str:
            end_date = timezone.datetime.fromisoformat(end_date_str)

        message_obj = Message.objects.create(sender=sender, recipient=recipient, content=message, start_date=start_date, end_date=end_date)
        return message_obj.timestamp

    @sync_to_async
    def get_message_history(self, start_date_str=None, end_date_str=None):
        user1, user2 = self.room_name.split("_")
        sender = User.objects.get(username=self.scope['user'].username)
        
        if self.scope['user'].username == user1:
            recipient_username = user2
        else:
            recipient_username = user1
        recipient = User.objects.get(username=recipient_username)
        

        
        messages_base = Message.objects.filter(
        (Q(sender=sender, recipient=recipient) | Q(sender=recipient, recipient=sender))
        )

        total_messages_count = messages_base.count()
        start_index = total_messages_count - 20
        if start_index < 0:
            start_index = 0

        messages = Message.objects.filter(
            (Q(sender=sender, recipient=recipient) | Q(sender=recipient, recipient=sender))
        ).order_by('timestamp')[start_index:]
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                messages = messages.filter(timestamp__date__gte=start_date)
            except ValueError:
                print("Некорректный формат даты начала")

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                messages = messages.filter(timestamp__date__lte=end_date)
            except ValueError:
                print("Некорректный формат даты окончания")
        
        return [
            {
                'message': message.content,
                'sender': message.sender.username,
                'timestamp': message.timestamp.isoformat() if message.timestamp else None, # Убрали timezone.localtime
                'start_date': message.start_date.isoformat() if message.start_date else None,
                'end_date': message.end_date.isoformat() if message.end_date else None,
            }
            for message in messages
        ]
    

    @sync_to_async
    def mark_messages_as_read(self, recipient_username):
        user1, user2 = self.room_name.split("_")
        sender = User.objects.get(username=self.scope['user'].username)

        if self.scope['user'].username == user1:
            recipient_username = user2
        else:
            recipient_username = user1
        recipient = User.objects.get(username=recipient_username)


        Message.objects.filter(sender=recipient, recipient=sender, is_read=False).update(is_read=True)