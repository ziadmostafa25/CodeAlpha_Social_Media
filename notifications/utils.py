import logging
from .models import Notification

logger = logging.getLogger(__name__)


def create_notification(actor, recipient, verb, post=None, reel=None):
    """
    Helper to dispatch a notification to a recipient, ignoring self-actions and checking preferences.
    Uses robust error handling with logging rather than silent exception suppression.
    """
    if not actor or not recipient or actor == recipient:
        return None

    try:
        # Check user notification preferences if configured on profile
        if hasattr(recipient, 'profile'):
            profile = recipient.profile
            if verb in ('like', 'reel_like') and not profile.notify_likes:
                return None
            if verb == 'comment' and not profile.notify_comments:
                return None
            if verb in ('follow', 'follow_request', 'follow_accepted') and not profile.notify_follows:
                return None
            if verb == 'message' and not profile.notify_messages:
                return None
            if verb == 'repost' and not profile.notify_reposts:
                return None

        return Notification.objects.create(
            actor=actor,
            recipient=recipient,
            verb=verb,
            post=post,
            reel=reel
        )
    except Exception as e:
        logger.exception("Failed to create notification %s -> %s (%s): %s", actor, recipient, verb, e)
        return None
