from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import SMSMessage
from django.db import models
from .forms import MessageForm
from django.http import JsonResponse
from django.utils import timezone
import datetime
import time
from django.http import HttpResponse
import traceback
from django.db.models import Q



@login_required(login_url='login')
def MainPage(request):
	users = User.objects.exclude(id=request.user.id)  # Получаем всех пользователей, кроме текущего
	context = {'users': users}
	return render(request, "chat/Mainpage.html", context)


@login_required(login_url='login')
def chat_view(request, recipient_username):
    users = User.objects.exclude(id=request.user.id)
    recipient = get_object_or_404(User, username=recipient_username)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            SMSMessage.objects.create(sender=request.user, recipient=recipient, message=message)
            return redirect('chat', recipient_username=recipient_username)
    else:
        form = MessageForm()

    total_messages_count = SMSMessage.objects.filter(
        (models.Q(sender=request.user, recipient=recipient) | models.Q(sender=recipient, recipient=request.user))
    ).count()

    start_index = max(0, total_messages_count - 20)

    messages = SMSMessage.objects.filter(
    	(models.Q(sender=request.user, recipient=recipient) | models.Q(sender=recipient, recipient=request.user))
    	).order_by('timestamp')[start_index:]

    context = {
    	'users':users,
        'form': form,
        'messages': messages,
        'recipient': recipient,
    }
    return render(request, 'chat/chat.html', context)


@login_required(login_url='login')
def get_new_messages(request, recipient_username):
    recipient = get_object_or_404(User, username=recipient_username)
    last_message_id = request.GET.get('last_message_id')

    if last_message_id and last_message_id != 'null': # Проверяем, что last_message_id не равен null
        try:
            last_message_id = int(last_message_id)
            new_messages = SMSMessage.objects.filter(
                (models.Q(sender=request.user, recipient=recipient) | models.Q(sender=recipient, recipient=request.user)),
                id__gt=last_message_id
            ).order_by('timestamp')
        except ValueError:
            # Обрабатываем случай, когда last_message_id не является целым числом
            print(f"Invalid last_message_id: {last_message_id}")
            return JsonResponse({'messages': []}) # Возвращаем пустой список сообщений
    else:
        new_messages = SMSMessage.objects.filter(
            (models.Q(sender=request.user, recipient=recipient) | models.Q(sender=recipient, recipient=request.user))
        ).order_by('timestamp')


    messages_data = []
    for message in new_messages:
        messages_data.append({
            'id': message.id,
            'sender': message.sender.username,
            'sender_first_name': message.sender.first_name,
            'message': message.message,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': message.is_read,
        })
    return JsonResponse({'messages': messages_data})


@login_required  # Теперь функция требует аутентификации
def mark_as_read(request, message_id):
    message = get_object_or_404(SMSMessage, id=message_id)  # Используем get_object_or_404
    if message.recipient == request.user:
        message.is_read = True
        message.save()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Нельзя пометить чужое сообщение как прочитанное'}, status=403)


@login_required
def get_unread_count_long_polling(request):
    recipient_username = request.GET.get('recipient_username')
    if not recipient_username:
        return JsonResponse({'error': 'recipient_username is required'}, status=400)

    try:
        recipient = User.objects.get(username=recipient_username)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error getting recipient: {e}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

    last_count = int(request.GET.get('last_count', 0))

    timeout = 60
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Count unread messages sent TO the current user FROM the recipient.
            unread_count = SMSMessage.objects.filter(
                recipient=request.user,  # Messages TO the current user
                sender=recipient,       # Messages FROM the recipient
                is_read=False
            ).count()
            
            print(f"Unread count for {recipient_username}: {unread_count}, Last count: {last_count}")

            if unread_count != last_count:
                return JsonResponse({'unread_count': unread_count})

            time.sleep(5)
        except Exception as e:
            print(f"Error counting messages: {e}")
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

    try:
        # Count again after timeout
        unread_count = SMSMessage.objects.filter(
              recipient=request.user,  # Messages TO the current user
                sender=recipient,       # Messages FROM the recipient
                is_read=False
        ).count()
        return JsonResponse({'unread_count': unread_count})
    except Exception as e:
        print(f"Error counting messages after timeout: {e}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)