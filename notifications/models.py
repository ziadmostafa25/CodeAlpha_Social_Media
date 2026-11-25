from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from posts.models import Post, Reel


class Notification(models.Model):
    """Notification event for user interactions (likes, comments, follows, reposts, messages)."""
    VERB_CHOICES = (
        ('like', _('liked your post')),
        ('comment', _('commented on your post')),
        ('follow', _('started following you')),
        ('follow_request', _('requested to follow you')),
        ('follow_accepted', _('accepted your follow request')),
        ('repost', _('reposted your story')),
        ('message', _('sent you a direct message')),
        ('mention', _('mentioned you in a post')),
        ('reel_like', _('liked your reel')),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    verb = models.CharField(_("Action"), max_length=25, choices=VERB_CHOICES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(_("Read"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"Notification: {self.actor.username} {self.verb} -> {self.recipient.username}"
