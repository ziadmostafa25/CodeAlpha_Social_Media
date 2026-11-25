from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from .models import Notification


@login_required
def notifications_list_view(request):
    """
    Display all notifications for the authenticated user.
    Pure read operation on GET request (does NOT modify database state on GET).
    """
    notifications = request.user.notifications.select_related(
        'actor', 'actor__profile', 'post', 'reel'
    ).all()

    return render(request, 'notifications/notification_list.html', {
        'notifications': notifications[:50]
    })


@login_required
def mark_notification_read_view(request, notification_id):
    """Mark a single notification as read using POST."""
    if request.method != 'POST':
        return redirect('notifications:list')

    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})

    return redirect('notifications:list')


@login_required
def mark_all_read_view(request):
    """Mark all user notifications as read using POST."""
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok'})
        messages.success(request, _("All notifications marked as read."))

    return redirect('notifications:list')
