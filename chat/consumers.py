import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.models import User
from .models import Message
from channels.layers import get_channel_layer
from django.db.models import Q
from datetime import datetime
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from asgiref.sync import sync_to_async

online_users = {}
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name
        self.user = self.scope['user']
        self.notification_group_name = f"notification_{self.user.username}"  #  Имя группы уведомлений

        await self.accept()
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        online_users[self.user.username] = {self.channel_name} # сет с channel_name
        print(f"User {self.user.username} connected. Online users: {online_users}")

        
        await self.send_online_users()
        messages = await self.get_message_history()
        await self.send(text_data=json.dumps({
            'type': 'message_history',
            'messages': messages
        }, cls=DjangoJSONEncoder))
        

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            self.notification_group_name,
            self.channel_name
        )
        if self.user.username in online_users:
            online_users[self.user.username].remove(self.channel_name)
            if not online_users[self.user.username]:
                del online_users[self.user.username]
        print(f"User {self.user.username} disconnected. Online users: {online_users}")

        await self.send_online_users()

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            sender_username = self.scope['user'].username
            recipient_username = self.room_name.replace(sender_username, '').replace('_','')

            print(f"Sender: {sender_username}, Recipient: {recipient_username}")
            print(f"Online users: {online_users}")

            # Проверяем, есть ли recipient_username в online_users
            if recipient_username not in online_users:
                print(f"Sending notification to {recipient_username}")
                await self.send_notification(recipient_username, message)
            else:
                print(f"Recipient {recipient_username} is online. Not sending notification.")

            
            timestamp = await self.save_message(sender_username, self.room_name, message, None, None)

            
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
        print(f"CHAT_MESSAGE: event={event}")
        message = event['message']
        sender_username = event['sender']
        timestamp = event['timestamp']
        start_date = event.get('start_date')
        end_date = event.get('end_date')

        # Получаем объект пользователя для получения first_name
        user = await self.get_user(sender_username)
        sender_first_name = user.first_name

        formatted_timestamp = timezone.datetime.fromisoformat(timestamp).strftime('%H+3:%M %d.%m.%Y')

        
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': message,
            'sender': sender_username,
            'sender_first_name': sender_first_name,  # Добавляем first_name
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

        
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': message,
        }))
    async def send_online_users(self):
        online_users_list = list(online_users.keys()) # Получаем список имен пользователей онлайн

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'update_online_users',
                'users': online_users_list
            }
        )

    async def update_online_users(self, event):
        users = event['users']
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': users
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
        print("get_message_history called")
        user1, user2 = self.room_name.split("_")
        print(f"Room name: {self.room_name}, User1: {user1}, User2: {user2}")
        try:
            sender = User.objects.get(username=self.scope['user'].username)
            if self.scope['user'].username == user1:
                recipient_username = user2
            else:
                recipient_username = user1
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            print(f"User not found")
            return []

        messages_base = Message.objects.filter(
            (Q(sender=sender, recipient=recipient) | Q(sender=recipient, recipient=sender))
        )

        total_messages_count = messages_base.count()
        start_index = total_messages_count - 20
        if start_index < 0:
            start_index = 0

        messages = Message.objects.filter(
            (Q(sender=sender, recipient=recipient) | Q(sender=recipient, recipient=sender))
        ).order_by('timestamp')

        
        messages_to_update = messages.all()  

        
        messages = messages[start_index:]

        
        messages_to_update.filter(recipient=sender, is_read=False).update(is_read=True)

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

        message_list = [
            {
                'message': message.content,
                'sender': message.sender.username,
                'timestamp': message.timestamp.strftime('%H:%M %d.%m.%Y') if message.timestamp else None,
                'is_read': message.is_read,
            }
            for message in messages
        ]
        print(f"get_message_history returning {len(message_list)} messages")
        return message_list


    async def messages_read(self, event):
        count = event['count']
        print(f"messages_read event called, updated {count} messages")
        await self.send(text_data=json.dumps({
            'type': 'messages_read',
            'count': count,
        }))

    @sync_to_async
    def get_user(self, username):
        return User.objects.get(username=username)
