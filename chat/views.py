from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Message
from django.db import models
from django.db.models import Q
from django.db.models import Count


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
    users = User.objects.exclude(id=current_user.id)


    room_name = get_room_name(current_user.username, recipient.username)
    unread_counts = {}
    for user in users:
        unread_count = Message.objects.filter(sender=user, recipient=request.user, is_read=False).count()
        unread_counts[user.username] = unread_count

    
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
        'unread_counts': unread_counts,
        'recipient_username': recipient.username,
    }
    return render(request, 'chat/index.html', context)


@login_required(login_url='login')
def MainPage(request):
    users = User.objects.exclude(id=request.user.id)
    main = request.user.username

    unread_counts = {}
    for user in users:
        unread_count = Message.objects.filter(sender=user, recipient=request.user, is_read=False).count()
        unread_counts[user.username] = unread_count
        
    context = {
        'users': users,
        'main': main,
        'unread_counts': unread_counts,
    }

    return render(request, "chat/Mainpage.html", context)