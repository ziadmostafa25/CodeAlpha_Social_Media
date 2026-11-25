
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.utils.translation import gettext as _

from .models import Conversation, Message, MessageReaction
from .forms import MessageForm
from accounts.models import Block
from accounts.permissions import can_message_user, is_user_blocked
from notifications.utils import create_notification


@login_required
def inbox_view(request):
    """Inbox listing all conversations of the authenticated user."""
    conversations = request.user.conversations.prefetch_related(
        'participants', 'participants__profile', 'messages'
    ).order_by('-updated_at')

    blocked_ids = set(
        Block.objects.filter(blocker=request.user).values_list(
            'blocked_id', flat=True
        )
    )
    blocker_ids = set(
        Block.objects.filter(blocked=request.user).values_list(
            'blocker_id', flat=True
        )
    )
    restricted_user_ids = blocked_ids.union(blocker_ids)

    following_users = User.objects.filter(
        followers_set__follower=request.user,
        followers_set__is_accepted=True
    ).exclude(
        id__in=list(restricted_user_ids) + [request.user.id]
    ).select_related('profile')[:10]

    return render(request, 'chat/inbox.html', {
        'conversations': conversations,
        'following_users': following_users,
    })


@login_required
def start_conversation_view(request, username):
    """
    Start or view conversation with another user.
    GET requests NEVER create database records.
    """
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        messages.warning(
            request,
            _("You cannot start a conversation with yourself.")
        )
        return redirect('chat:inbox')

    if is_user_blocked(request.user, other_user):
        messages.error(request, _("Cannot message a blocked user."))
        return redirect('accounts:profile', username=username)

    if not can_message_user(request.user, other_user):
        messages.error(
            request,
            _("@%(username)s does not accept direct messages from you.")
            % {'username': other_user.username}
        )
        return redirect('accounts:profile', username=username)

    existing_conv = None
    convs = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user)

    for c in convs:
        if c.participants.count() == 2:
            existing_conv = c
            break

    if existing_conv:
        return redirect(
            'chat:conversation',
            conversation_id=existing_conv.id
        )

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)

        if form.is_valid():
            conversation, created = Conversation.get_or_create_direct(
                request.user, other_user
            )

            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()

            conversation.save()

            create_notification(
                actor=request.user,
                recipient=other_user,
                verb='message'
            )

            messages.success(request, _("Conversation started!"))

            return redirect(
                'chat:conversation',
                conversation_id=conversation.id
            )

        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)

    else:
        form = MessageForm()

    all_conversations = request.user.conversations.prefetch_related(
        'participants', 'participants__profile', 'messages'
    ).order_by('-updated_at')

    return render(request, 'chat/conversation.html', {
        'conversation': None,
        'other_user': other_user,
        'messages_list': [],
        'form': form,
        'all_conversations': all_conversations,
        'is_new_thread': True,
    })


@login_required
def conversation_view(request, conversation_id):
    """
    View conversation thread and send messages.
    Blocked users cannot access or send messages in an existing conversation.
    """
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related(
            'participants', 'participants__profile'
        ),
        id=conversation_id
    )

    if request.user not in conversation.participants.all():
        return HttpResponseForbidden(
            _("You are not a participant in this conversation.")
        )

    other_user = conversation.get_other_participant(request.user)

    # Block protection
    if other_user and is_user_blocked(request.user, other_user):
        return HttpResponseForbidden(
            _("You cannot access this conversation because messaging is restricted.")
        )

    if request.method == 'POST':
        # Recheck before sending a message
        if other_user and is_user_blocked(request.user, other_user):
            return HttpResponseForbidden(
                _("You cannot send messages to this user.")
            )

        form = MessageForm(request.POST, request.FILES)

        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = conversation
            msg.sender = request.user
            msg.save()

            conversation.save()

            if other_user:
                create_notification(
                    actor=request.user,
                    recipient=other_user,
                    verb='message'
                )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'message_id': msg.id,
                    'content': msg.content,
                    'attachment_url': msg.attachment.url if msg.attachment else None,
                    'audio_url': msg.audio_file.url if msg.audio_file else None,
                    'audio_duration': msg.audio_duration,
                    'sender_username': msg.sender.username,
                    'created_at': _("Just now"),
                })

            return redirect(
                'chat:conversation',
                conversation_id=conversation.id
            )

        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'error', 'errors': form.errors},
                    status=400
                )

    else:
        form = MessageForm()

    q = request.GET.get('q', '').strip()

    messages_qs = (
        conversation.messages
        .select_related('sender', 'sender__profile', 'reply_to')
        .prefetch_related('reactions')
        .order_by('created_at')
    )

    if q:
        messages_qs = messages_qs.filter(content__icontains=q)

    all_conversations = request.user.conversations.prefetch_related(
        'participants', 'participants__profile', 'messages'
    ).order_by('-updated_at')

    return render(request, 'chat/conversation.html', {
        'conversation': conversation,
        'other_user': other_user,
        'messages_list': messages_qs,
        'form': form,
        'all_conversations': all_conversations,
        'search_query': q,
    })


@login_required
def mark_conversation_read_view(request, conversation_id):
    """Explicit authenticated POST endpoint to mark messages as read."""
    if request.method != 'POST':
        return HttpResponseForbidden(
            _("Only POST is permitted for state change.")
        )

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id
    )

    if request.user not in conversation.participants.all():
        return HttpResponseForbidden(
            _("You are not a participant in this conversation.")
        )

    updated_count = conversation.messages.filter(
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    return JsonResponse({
        'status': 'ok',
        'updated_count': updated_count,
    })


@login_required
def poll_messages_view(request, conversation_id):
    """Poll for new messages without modifying read status."""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id
    )

    if request.user not in conversation.participants.all():
        return HttpResponseForbidden(
            _("You are not a participant in this conversation.")
        )

    try:
        last_id = int(request.GET.get('last_id', 0))
    except (ValueError, TypeError):
        last_id = 0

    new_msgs = conversation.messages.filter(
        id__gt=last_id
    ).select_related(
        'sender', 'sender__profile', 'reply_to'
    ).order_by('created_at')

    data = []

    for m in new_msgs:
        data.append({
            'id': m.id,
            'sender_id': m.sender.id,
            'sender_username': m.sender.username,
            'is_me': m.sender == request.user,
            'content': m.content,
            'attachment_url': m.attachment.url if m.attachment else None,
            'audio_url': m.audio_file.url if m.audio_file else None,
            'audio_duration': m.audio_duration,
            'created_at': m.created_at.strftime('%H:%M'),
        })

    return JsonResponse({
        'status': 'ok',
        'messages': data
    })


@login_required
def message_react_view(request, message_id):
    """Toggle emoji reaction on a message. Requires POST."""
    if request.method != 'POST':
        return HttpResponseForbidden(_("Only POST allowed."))

    msg = get_object_or_404(Message, id=message_id)

    if request.user not in msg.conversation.participants.all():
        return HttpResponseForbidden(_("Not authorized."))

    emoji = request.POST.get('emoji', '❤️')

    reaction_qs = MessageReaction.objects.filter(
        message=msg,
        user=request.user,
        emoji=emoji
    )

    if reaction_qs.exists():
        reaction_qs.delete()
        is_reacted = False
    else:
        MessageReaction.objects.create(
            message=msg,
            user=request.user,
            emoji=emoji
        )
        is_reacted = True

    return JsonResponse({
        'status': 'ok',
        'is_reacted': is_reacted,
        'emoji': emoji,
        'reactions_count': msg.reactions.count(),
    })


@login_required
def delete_message_view(request, message_id):
    """Delete a user's own message. Requires POST."""
    if request.method != 'POST':
        return HttpResponseForbidden(_("Only POST allowed."))

    msg = get_object_or_404(Message, id=message_id)

    if msg.sender != request.user:
        return HttpResponseForbidden(
            _("You are not authorized to delete this message.")
        )

    conv_id = msg.conversation.id
    msg.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})

    messages.success(request, _("Message deleted."))

    return redirect(
        'chat:conversation',
        conversation_id=conv_id
    )
