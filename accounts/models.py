from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    """Extended user profile containing avatar, cover banner, bio, privacy, and preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(_("Display Name"), max_length=100, blank=True)
    bio = models.TextField(_("Bio"), max_length=500, blank=True)
    avatar = models.ImageField(_("Avatar"), upload_to='avatars/%Y/%m/', blank=True, null=True)
    cover_image = models.ImageField(_("Cover Image"), upload_to='covers/%Y/%m/', blank=True, null=True)
    location = models.CharField(_("Location"), max_length=100, blank=True)
    website = models.URLField(_("Website"), max_length=200, blank=True)
    
    # Privacy & Safety Settings
    is_private = models.BooleanField(_("Private Account"), default=False)
    allow_messages_from = models.CharField(
        _("Who Can Message You"),
        max_length=20,
        choices=(('everyone', _('Everyone')), ('followers', _('Followers Only')), ('none', _('No One'))),
        default='everyone'
    )

    # Notification Preferences
    notify_likes = models.BooleanField(_("Notify on Likes"), default=True)
    notify_comments = models.BooleanField(_("Notify on Comments"), default=True)
    notify_follows = models.BooleanField(_("Notify on Follows"), default=True)
    notify_messages = models.BooleanField(_("Notify on Messages"), default=True)
    notify_reposts = models.BooleanField(_("Notify on Reposts"), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user.username} ({self.get_display_name})"

    @property
    def get_display_name(self):
        return self.display_name if self.display_name else self.user.username

    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None

    def get_cover_url(self):
        if self.cover_image and hasattr(self.cover_image, 'url'):
            return self.cover_image.url
        return None


class Follow(models.Model):
    """Follow relationship between users with uniqueness, self-follow validation, and request states."""
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers_set')
    is_accepted = models.BooleanField(_("Accepted"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Follow")
        verbose_name_plural = _("Follows")
        unique_together = ('follower', 'following')
        indexes = [
            models.Index(fields=['follower', 'following']),
            models.Index(fields=['-created_at']),
        ]

    def clean(self):
        if self.follower == self.following:
            raise ValidationError(_("Users cannot follow themselves."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "" if self.is_accepted else " (Pending)"
        return f"@{self.follower.username} follows @{self.following.username}{status}"


class Block(models.Model):
    """User block relationship preventing interaction, messaging, and content viewing."""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocking')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Block")
        verbose_name_plural = _("Blocks")
        unique_together = ('blocker', 'blocked')
        indexes = [
            models.Index(fields=['blocker', 'blocked']),
        ]

    def clean(self):
        if self.blocker == self.blocked:
            raise ValidationError(_("Users cannot block themselves."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"@{self.blocker.username} blocked @{self.blocked.username}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
