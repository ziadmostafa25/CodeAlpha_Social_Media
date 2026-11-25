
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.translation import gettext as _

from .models import Conversation, Message, MessageReaction
from .forms import MessageForm
from accounts.models import Block
from accounts.permissions import can_message_user, is_user_blocked
from notifications.utils import create_notification


def _conversation_access_allowed(conversation, user):
    if not conversation.participants.filter(id=user.id).exists():
        return False

    other_user = conversation.get_other_participant(user)

    return not (
        other_user and is_user_blocked(user, other_user)
    )


@login_required
def inbox_view(request):
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
            if form.cleaned_data.get('reply_to'):
                form.add_error(
                    'reply_to',
                    _("You cannot reply to a message in a new conversation.")
                )
            else:
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
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related(
            'participants', 'participants__profile'
        ),
        id=conversation_id
    )

    if not _conversation_access_allowed(conversation, request.user):
        return HttpResponseForbidden(
            _("You cannot access this conversation.")
        )

    other_user = conversation.get_other_participant(request.user)

    if request.method == 'POST':
        if not _conversation_access_allowed(conversation, request.user):
            return HttpResponseForbidden(
                _("You cannot send messages to this user.")
            )

        form = MessageForm(request.POST, request.FILES)

        if form.is_valid():
            reply_to = form.cleaned_data.get('reply_to')

            if reply_to and reply_to.conversation_id != conversation.id:
                form.add_error(
                    'reply_to',
                    _("You can only reply to messages in this conversation.")
                )
            else:
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
    if request.method != 'POST':
        return HttpResponseForbidden(
            _("Only POST is permitted for state change.")
        )

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id
    )

    if not _conversation_access_allowed(conversation, request.user):
        return HttpResponseForbidden(
            _("You are not allowed to access this conversation.")
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
    if request.method != 'GET':
        return HttpResponseForbidden(_("Only GET is permitted."))

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id
    )

    if not _conversation_access_allowed(conversation, request.user):
        return HttpResponseForbidden(
            _("You are not allowed to access this conversation.")
        )

    try:
        last_id = int(request.GET.get('last_id', 0))
    except (ValueError, TypeError):
        last_id = 0

    last_id = max(last_id, 0)

    new_msgs = conversation.messages.filter(
        id__gt=last_id
    ).select_related(
        'sender', 'sender__profile', 'reply_to'
    ).order_by('created_at')[:100]

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
    if request.method != 'POST':
        return HttpResponseForbidden(_("Only POST allowed."))

    msg = get_object_or_404(Message, id=message_id)

    if not _conversation_access_allowed(msg.conversation, request.user):
        return HttpResponseForbidden(_("Not authorized."))

    emoji = request.POST.get('emoji', '❤️').strip()

    if not emoji or len(emoji) > 16:
        return JsonResponse(
            {'status': 'error', 'message': _('Invalid reaction.')},
            status=400
        )

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
