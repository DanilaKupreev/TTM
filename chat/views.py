from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Message
from django.db import models
from django.db.models import Q


def get_room_name(user1, user2):
    usernames = sorted([user1, user2])
    return f"{usernames[0]}_{usernames[1]}"


@login_required
def chat_view(request):
    recipient_username = request.GET.get('recipient')  # Получаем имя получателя из GET-параметра
    if not recipient_username:
        return redirect('chat')  # Если получатель не указан, возвращаемся на главную страницу чата

    recipient = User.objects.get(username=recipient_username)
    firstname1 = recipient.first_name
    current_user = request.user

    room_name = get_room_name(current_user.username, recipient.username)

    users = User.objects.exclude(id=current_user.id)
    total_messages_count = Message.objects.filter(
        (Q(sender=current_user, recipient=recipient) | Q(sender=recipient, recipient=current_user))
    ).count()

    start_index = max(0, total_messages_count - 20)

    messages = Message.objects.filter(
        (Q(sender=current_user, recipient=recipient) | Q(sender=recipient, recipient=current_user))
    ).order_by('timestamp')[start_index:].select_related('sender', 'recipient')

    context = {
        'users': users,
        'messages': messages,
        'recipient': recipient,
        'main': current_user.username,  # Передаем имя текущего пользователя
        'room_name': room_name,  # Передаем имя комнаты
        'recipient_username': recipient.username,
    }
    return render(request, 'chat/index.html', context)


@login_required(login_url='login')
def MainPage(request):
    users = User.objects.exclude(id=request.user.id)
    main = request.user.username
    context = {
        'users': users,
        'main': main,
    }

    return render(request, "chat/Mainpage.html", context)