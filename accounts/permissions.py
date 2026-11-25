from django.db.models import Q
from .models import Follow, Block


def is_user_blocked(user1, user2):
    """Check if either user has blocked the other."""
    if not user1 or not user2 or not user1.is_authenticated or not user2.is_authenticated:
        return False
    if user1 == user2:
        return False
    return Block.objects.filter(
        Q(blocker=user1, blocked=user2) | Q(blocker=user2, blocked=user1)
    ).exists()


def can_view_user_content(viewer, target_user):
    """
    Shared permission logic: check if viewer can view target_user's posts, reels, reposts, and profile content.
    - An owner can always view their own content.
    - If blocked (in either direction), content is strictly hidden.
    - If target_user is public (not is_private), content is viewable by all non-blocked users.
    - If target_user is private:
      - Anonymous viewers CANNOT view content.
      - Authenticated viewers can only view if they have an ACCEPTED follow relationship.
      - Pending follow requests (is_accepted=False) DO NOT grant access.
    """
    if not target_user:
        return False

    # Owner can always see their own content
    if viewer and viewer.is_authenticated and viewer.id == target_user.id:
        return True

    # Check for blocking
    if viewer and viewer.is_authenticated and is_user_blocked(viewer, target_user):
        return False

    # Check if target account is private
    is_private = hasattr(target_user, 'profile') and target_user.profile.is_private
    if not is_private:
        return True

    # Account is private: viewer must be authenticated and have an accepted follow
    if not viewer or not viewer.is_authenticated:
        return False

    return Follow.objects.filter(
        follower=viewer,
        following=target_user,
        is_accepted=True
    ).exists()


def can_message_user(sender, recipient):
    """
    Check if sender is permitted to message recipient based on privacy settings and blocking.
    """
    if not sender or not recipient or not sender.is_authenticated:
        return False
    if sender == recipient:
        return False
    if is_user_blocked(sender, recipient):
        return False

    if hasattr(recipient, 'profile'):
        perm = recipient.profile.allow_messages_from
        if perm == 'none':
            return False
        if perm == 'followers':
            # Sender must be accepted follower of recipient
            return Follow.objects.filter(
                follower=sender,
                following=recipient,
                is_accepted=True
            ).exists()
    return True
