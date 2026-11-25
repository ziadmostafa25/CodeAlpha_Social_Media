def unread_messages_count(request):
    """Provide count of unread messages for authenticated user."""
    if request.user.is_authenticated:
        try:
            from chat.models import Message
            count = Message.objects.filter(
                conversation__participants=request.user,
                is_read=False
            ).exclude(sender=request.user).count()
            return {'unread_messages_count': count}
        except Exception:
            return {'unread_messages_count': 0}
    return {'unread_messages_count': 0}
