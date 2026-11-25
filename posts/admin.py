from django.contrib import admin
from .models import Post, Comment, Like, Repost, SavedPost, Report, Reel, ReelLike, ReelComment


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'content_snippet', 'likes_count', 'comments_count', 'reposts_count', 'created_at')
    search_fields = ('author__username', 'content')
    list_filter = ('created_at',)

    def content_snippet(self, obj):
        return (obj.content[:40] + '...') if len(obj.content) > 40 else obj.content
    content_snippet.short_description = 'Content'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'author', 'content', 'created_at')
    search_fields = ('author__username', 'content')
    list_filter = ('created_at',)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'created_at')
    search_fields = ('user__username',)
    list_filter = ('created_at',)


@admin.register(Repost)
class RepostAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'post', 'created_at')
    search_fields = ('user__username',)
    list_filter = ('created_at',)


@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'post', 'created_at')
    search_fields = ('user__username',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'post', 'reason', 'created_at')
    list_filter = ('reason', 'created_at')


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'caption_snippet', 'views_count', 'created_at')
    search_fields = ('author__username', 'caption')

    def caption_snippet(self, obj):
        return (obj.caption[:30] + '...') if len(obj.caption) > 30 else obj.caption
