from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class Post(models.Model):
    """User published post containing text caption, optional media image, and interaction metadata."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(_("Content"), blank=True)
    image = models.ImageField(_("Image"), upload_to='posts/%Y/%m/', blank=True, null=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Post")
        verbose_name_plural = _("Posts")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def clean(self):
        if not self.content.strip() and not self.image:
            raise ValidationError(_("A post must contain either text content or an image."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        snippet = (self.content[:30] + '...') if len(self.content) > 30 else (self.content or "[Image Post]")
        return f"Post #{self.pk} by @{self.author.username}: {snippet}"

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()

    @property
    def reposts_count(self):
        return self.reposts.count()

    @property
    def saves_count(self):
        return self.saved_by.count()

    def is_liked_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def is_reposted_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.reposts.filter(user=user).exists()

    def is_saved_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.saved_by.filter(user=user).exists()


class Comment(models.Model):
    """User comment attached to a post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(_("Comment"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'created_at']),
            models.Index(fields=['author']),
        ]

    def clean(self):
        if not self.content or not self.content.strip():
            raise ValidationError(_("Comment content cannot be empty."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comment by @{self.author.username} on Post #{self.post_id}"


class Like(models.Model):
    """Post like by a user with unique constraint to prevent duplicate likes."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_posts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Like")
        verbose_name_plural = _("Likes")
        unique_together = ('post', 'user')
        indexes = [
            models.Index(fields=['post', 'user']),
        ]

    def __str__(self):
        return f"@{self.user.username} liked Post #{self.post_id}"


class Repost(models.Model):
    """Post repost by a user displaying in feed with attribution."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reposts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reposts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Repost")
        verbose_name_plural = _("Reposts")
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user.username} reposted Post #{self.post_id}"


class SavedPost(models.Model):
    """Saved post bookmark for a user's private collection."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Saved Post")
        verbose_name_plural = _("Saved Posts")
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user.username} saved Post #{self.post_id}"


class Reel(models.Model):
    """Vertical short-form video post for the Reels experience."""
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    caption = models.TextField(_("Caption"), blank=True)
    video = models.FileField(_("Video File"), upload_to='reels/%Y/%m/')
    thumbnail = models.ImageField(_("Thumbnail"), upload_to='reels/thumbs/%Y/%m/', blank=True, null=True)
    sound_title = models.CharField(_("Sound Title"), max_length=150, blank=True, default="Original Sound")
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Reel")
        verbose_name_plural = _("Reels")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        snippet = (self.caption[:30] + '...') if len(self.caption) > 30 else (self.caption or "[Video Reel]")
        return f"Reel #{self.pk} by @{self.author.username}: {snippet}"

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()


class ReelLike(models.Model):
    """Like interaction on a Reel video."""
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reel_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Reel Like")
        verbose_name_plural = _("Reel Likes")
        unique_together = ('reel', 'user')


class ReelComment(models.Model):
    """Comment on a Reel video."""
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reel_comments')
    content = models.TextField(_("Comment"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Reel Comment")
        verbose_name_plural = _("Reel Comments")
        ordering = ['created_at']


class SavedReel(models.Model):
    """Saved reel bookmark for a user's private collection."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_reels')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Saved Reel")
        verbose_name_plural = _("Saved Reels")
        unique_together = ('user', 'reel')
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.user.username} saved Reel #{self.reel_id}"


class Report(models.Model):
    """Content report submitted by users for moderation."""
    REASON_CHOICES = (
        ('spam', _('Spam or Scam')),
        ('harassment', _('Harassment or Bullying')),
        ('inappropriate', _('Inappropriate or Sensitive Content')),
        ('violence', _('Violence, Self-Harm, or Dangerous Threats')),
        ('copyright', _('Copyright or Intellectual Property Violation')),
        ('other', _('Other Issue')),
    )

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_submitted')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reason = models.CharField(_("Reason"), max_length=30, choices=REASON_CHOICES)
    details = models.TextField(_("Additional Details"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        ordering = ['-created_at']

    def __str__(self):
        target = f"Post #{self.post_id}" if self.post else f"Reel #{self.reel_id}"
        return f"Report #{self.id} on {target} by @{self.reporter.username}"
