from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
    """Chat thread between participants."""
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        ordering = ['-updated_at']

    def __str__(self):
        usernames = ", ".join([u.username for u in self.participants.all()[:2]])
        return f"Conversation ({usernames})"

    def get_other_participant(self, user):
        """Get the other person in a 1-on-1 conversation."""
        return self.participants.exclude(id=user.id).first()

    def last_message(self):
        return self.messages.order_by('-created_at').first()

    def get_last_message(self):
        return self.messages.order_by('-created_at').first()

    def unread_count_for(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    @classmethod
    def get_or_create_direct(cls, user1, user2):
        """
        Find an existing 1-on-1 conversation between user1 and user2 or create a new one.
        Ensures exactly 2 participants and prevents duplicates.
        """
        if user1 == user2:
            raise ValueError(_("Cannot create a conversation with yourself."))

        # Search conversations containing user1
        convs = cls.objects.filter(participants=user1).filter(participants=user2)
        for c in convs:
            if c.participants.count() == 2:
                return c, False

        # Create new conversation
        new_conv = cls.objects.create()
        new_conv.participants.add(user1, user2)
        return new_conv, True


class Message(models.Model):
    """Direct message within a conversation supporting text, images, voice audio, and replies."""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(_("Content"), blank=True)
    attachment = models.ImageField(_("Image Attachment"), upload_to='messages/%Y/%m/', blank=True, null=True)
    audio_file = models.FileField(_("Voice Message"), upload_to='voice_messages/%Y/%m/', blank=True, null=True)
    audio_duration = models.PositiveIntegerField(_("Duration (seconds)"), default=0, blank=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    is_read = models.BooleanField(_("Read"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ['created_at']

    def __str__(self):
        if self.audio_file:
            return f"Voice Message #{self.pk} from @{self.sender.username} ({self.audio_duration}s)"
        snippet = (self.content[:25] + '...') if len(self.content) > 25 else (self.content or "[Attachment]")
        return f"From @{self.sender.username}: {snippet}"


class MessageReaction(models.Model):
    """Emoji reaction on a specific message."""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_reactions')
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Message Reaction")
        verbose_name_plural = _("Message Reactions")
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"@{self.user.username} reacted {self.emoji} to Message #{self.message_id}"
