from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, F
from django.utils.translation import gettext as _

from .models import Post, Comment, Like, Repost, SavedPost, Report, Reel, ReelLike, ReelComment, SavedReel
from .forms import PostForm, CommentForm, ReelForm, ReportForm
from accounts.models import Follow, Block
from accounts.permissions import can_view_user_content, is_user_blocked
from notifications.utils import create_notification


def feed_view(request):
    """
    Main feed view: displays posts from accepted followings + own posts.
    Community fallback excludes private accounts and blocked users.
    """
    post_form = PostForm()
    comment_form = CommentForm()

    if request.user.is_authenticated:
        # Blocked users list
        blocked_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
        blocker_ids = set(Block.objects.filter(blocked=request.user).values_list('blocker_id', flat=True))
        restricted_user_ids = blocked_ids.union(blocker_ids)

        # Followed users with ACCEPTED follow requests
        following_ids = list(
            request.user.following_set.filter(is_accepted=True)
            .exclude(following_id__in=restricted_user_ids)
            .values_list('following_id', flat=True)
        )
        feed_user_ids = following_ids + [request.user.id]

        feed_posts = Post.objects.filter(author_id__in=feed_user_ids).select_related(
            'author', 'author__profile'
        ).prefetch_related('likes', 'comments', 'comments__author', 'comments__author__profile', 'reposts', 'saved_by')

        if feed_posts.count() < 8:
            # Fallback community posts: STRICTLY public accounts only, not blocked
            community_posts = Post.objects.filter(
                author__profile__is_private=False
            ).exclude(
                author_id__in=restricted_user_ids
            ).select_related(
                'author', 'author__profile'
            ).prefetch_related('likes', 'comments', 'comments__author', 'comments__author__profile', 'reposts', 'saved_by')
            posts = (feed_posts | community_posts).distinct().order_by('-created_at')
        else:
            posts = feed_posts.order_by('-created_at')

        user_liked_post_ids = set(request.user.liked_posts.values_list('post_id', flat=True))
        user_reposted_post_ids = set(request.user.reposts.values_list('post_id', flat=True))
        user_saved_post_ids = set(request.user.saved_posts.values_list('post_id', flat=True))

        suggested_users = User.objects.exclude(
            id__in=feed_user_ids + list(restricted_user_ids)
        ).select_related('profile')[:5]
    else:
        # Anonymous users: strictly public posts only
        posts = Post.objects.filter(
            author__profile__is_private=False
        ).select_related(
            'author', 'author__profile'
        ).prefetch_related('likes', 'comments', 'comments__author').order_by('-created_at')
        user_liked_post_ids = set()
        user_reposted_post_ids = set()
        user_saved_post_ids = set()
        suggested_users = User.objects.filter(profile__is_private=False).select_related('profile')[:5]

    context = {
        'posts': posts[:50],
        'post_form': post_form,
        'comment_form': comment_form,
        'user_liked_post_ids': user_liked_post_ids,
        'user_reposted_post_ids': user_reposted_post_ids,
        'user_saved_post_ids': user_saved_post_ids,
        'suggested_users': suggested_users,
    }
    return render(request, 'posts/feed.html', context)


def post_detail_view(request, post_id):
    """Detailed view for a single post with comments. Enforces private account restrictions."""
    post = get_object_or_404(
        Post.objects.select_related('author', 'author__profile').prefetch_related(
            'likes', 'comments__author', 'comments__author__profile', 'reposts', 'saved_by'
        ),
        pk=post_id
    )

    # Privacy check
    if not can_view_user_content(request.user, post.author):
        return HttpResponseForbidden(_("This post belongs to a private account."))

    # Safely increment view count
    Post.objects.filter(pk=post.pk).update(views_count=F('views_count') + 1)

    user_has_liked = False
    user_has_reposted = False
    user_has_saved = False

    if request.user.is_authenticated:
        user_has_liked = post.likes.filter(user=request.user).exists()
        user_has_reposted = post.reposts.filter(user=request.user).exists()
        user_has_saved = post.saved_by.filter(user=request.user).exists()

    context = {
        'post': post,
        'comments': post.comments.all(),
        'comment_form': CommentForm(),
        'user_has_liked': user_has_liked,
        'user_has_reposted': user_has_reposted,
        'user_has_saved': user_has_saved,
    }
    return render(request, 'posts/post_detail.html', context)


@login_required
def create_post_view(request):
    """Handle creation of a new post with text content and optional image."""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, _("Your story has been published on NIVO!"))
            return redirect('posts:feed')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    return redirect('posts:feed')


@login_required
def edit_post_view(request, post_id):
    """Allow author to edit their own post."""
    post = get_object_or_404(Post, pk=post_id)

    if post.author != request.user:
        return HttpResponseForbidden(_("You are not authorized to edit this post."))

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, _("Post updated successfully."))
            return redirect('posts:post_detail', post_id=post.id)
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = PostForm(instance=post)

    return render(request, 'posts/edit_post.html', {'form': form, 'post': post})


@login_required
def delete_post_view(request, post_id):
    """Allow author to delete their own post after confirmation. Requires POST."""
    post = get_object_or_404(Post, pk=post_id)

    if post.author != request.user:
        return HttpResponseForbidden(_("You are not authorized to delete this post."))

    if request.method == 'POST':
        post.delete()
        messages.success(request, _("Post has been deleted."))
        return redirect('posts:feed')

    return render(request, 'posts/delete_confirm.html', {'post': post})


@login_required
def like_toggle_view(request, post_id):
    """Toggle like on a post. Supports both AJAX and normal POST. Enforces privacy."""
    if request.method != 'POST':
        return redirect('posts:feed')

    post = get_object_or_404(Post, pk=post_id)

    if not can_view_user_content(request.user, post.author):
        return HttpResponseForbidden(_("Cannot like a private post without following."))

    like_qs = Like.objects.filter(post=post, user=request.user)

    if like_qs.exists():
        like_qs.delete()
        is_liked = False
    else:
        Like.objects.create(post=post, user=request.user)
        is_liked = True
        create_notification(actor=request.user, recipient=post.author, verb='like', post=post)

    likes_count = post.likes.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_liked': is_liked,
            'likes_count': likes_count,
        })

    return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')


@login_required
def repost_toggle_view(request, post_id):
    """Toggle repost of a post. Enforces privacy (cannot repost private posts)."""
    if request.method != 'POST':
        return redirect('posts:feed')

    post = get_object_or_404(Post, pk=post_id)

    # Private posts cannot be reposted
    if hasattr(post.author, 'profile') and post.author.profile.is_private:
        msg = _("Posts from private accounts cannot be reposted.")
        messages.error(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')

    if not can_view_user_content(request.user, post.author):
        return HttpResponseForbidden(_("Cannot repost content you cannot view."))

    repost_qs = Repost.objects.filter(post=post, user=request.user)

    if repost_qs.exists():
        repost_qs.delete()
        is_reposted = False
        message = _("Repost removed.")
    else:
        Repost.objects.create(post=post, user=request.user)
        is_reposted = True
        message = _("Reposted to your profile!")
        create_notification(actor=request.user, recipient=post.author, verb='repost', post=post)

    reposts_count = post.reposts.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_reposted': is_reposted,
            'reposts_count': reposts_count,
            'message': message,
        })

    messages.info(request, message)
    return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')


@login_required
def save_toggle_view(request, post_id):
    """Toggle bookmark / save post to private collection. Enforces privacy."""
    if request.method != 'POST':
        return redirect('posts:feed')

    post = get_object_or_404(Post, pk=post_id)

    if not can_view_user_content(request.user, post.author):
        return HttpResponseForbidden(_("Cannot save content you are not authorized to view."))

    saved_qs = SavedPost.objects.filter(post=post, user=request.user)

    if saved_qs.exists():
        saved_qs.delete()
        is_saved = False
        message = _("Removed from saved posts.")
    else:
        SavedPost.objects.create(post=post, user=request.user)
        is_saved = True
        message = _("Saved to your collection!")

    saves_count = post.saved_by.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_saved': is_saved,
            'saves_count': saves_count,
            'message': message,
        })

    messages.info(request, message)
    return redirect(request.META.get('HTTP_REFERER') or 'posts:feed')


@login_required
def saved_posts_view(request):
    """View all posts saved by the authenticated user, filtering out inaccessible private ones."""
    saved_items = SavedPost.objects.filter(
        user=request.user
    ).select_related('post', 'post__author', 'post__author__profile').prefetch_related(
        'post__likes', 'post__comments'
    ).order_by('-created_at')

    # Filter out posts from creators who became private and viewer does not follow
    posts = [item.post for item in saved_items if can_view_user_content(request.user, item.post.author)]

    user_liked_post_ids = set(request.user.liked_posts.values_list('post_id', flat=True))
    user_reposted_post_ids = set(request.user.reposts.values_list('post_id', flat=True))
    user_saved_post_ids = set(request.user.saved_posts.values_list('post_id', flat=True))

    return render(request, 'posts/saved_posts.html', {
        'posts': posts,
        'user_liked_post_ids': user_liked_post_ids,
        'user_reposted_post_ids': user_reposted_post_ids,
        'user_saved_post_ids': user_saved_post_ids,
    })


@login_required
def report_post_view(request, post_id):
    """Submit a report for a post."""
    post = get_object_or_404(Post, pk=post_id)

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.post = post
            report.save()
            messages.success(request, _("Thank you. Your report has been submitted for review."))
            return redirect('posts:post_detail', post_id=post.id)
    else:
        form = ReportForm()

    return render(request, 'posts/report_post.html', {
        'form': form,
        'post': post
    })


@login_required
def add_comment_view(request, post_id):
    """Add a new comment to a post. Enforces privacy permissions."""
    if request.method != 'POST':
        return redirect('posts:post_detail', post_id=post_id)

    post = get_object_or_404(Post, pk=post_id)

    if not can_view_user_content(request.user, post.author):
        return HttpResponseForbidden(_("Cannot comment on a post you are not authorized to view."))

    form = CommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()

        create_notification(actor=request.user, recipient=post.author, verb='comment', post=post)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            author_avatar = comment.author.profile.get_avatar_url() or ''
            return JsonResponse({
                'status': 'ok',
                'comment_id': comment.id,
                'author_username': comment.author.username,
                'author_display_name': comment.author.profile.get_display_name,
                'author_avatar': author_avatar,
                'content': comment.content,
                'created_at': _("Just now"),
                'comments_count': post.comments.count(),
            })

        messages.success(request, _("Comment added!"))
    else:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        messages.error(request, _("Comment could not be submitted."))

    return redirect(request.META.get('HTTP_REFERER') or 'posts:post_detail', post_id=post.id)


@login_required
def delete_comment_view(request, comment_id):
    """Delete comment if user is the comment author or post owner. Requires POST."""
    comment = get_object_or_404(Comment, pk=comment_id)

    if comment.author != request.user and comment.post.author != request.user:
        return HttpResponseForbidden(_("You are not authorized to delete this comment."))

    post_id = comment.post.id

    if request.method == 'POST':
        comment.delete()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            post = get_object_or_404(Post, pk=post_id)
            return JsonResponse({
                'status': 'ok',
                'message': _("Comment deleted."),
                'comments_count': post.comments.count(),
            })

        messages.success(request, _("Comment deleted."))

    return redirect(request.META.get('HTTP_REFERER') or 'posts:post_detail', post_id=post_id)


# ==============================================================================
# REELS & VIDEO EXPERIENCE
# ==============================================================================

def reels_feed_view(request):
    """
    Vertical short-form video feed for the Reels experience.
    Strictly filters out private reels from creators the viewer does not follow.
    """
    if request.user.is_authenticated:
        blocked_ids = set(Block.objects.filter(blocker=request.user).values_list('blocked_id', flat=True))
        blocker_ids = set(Block.objects.filter(blocked=request.user).values_list('blocker_id', flat=True))
        restricted_user_ids = blocked_ids.union(blocker_ids)

        following_ids = list(
            request.user.following_set.filter(is_accepted=True)
            .exclude(following_id__in=restricted_user_ids)
            .values_list('following_id', flat=True)
        )
        allowed_authors = following_ids + [request.user.id]

        reels = Reel.objects.filter(
            Q(author__profile__is_private=False) | Q(author_id__in=allowed_authors)
        ).exclude(
            author_id__in=restricted_user_ids
        ).select_related('author', 'author__profile').prefetch_related('likes', 'comments').order_by('-created_at')

        user_liked_reel_ids = set(request.user.reel_likes.values_list('reel_id', flat=True))
        user_saved_reel_ids = set(request.user.saved_reels.values_list('reel_id', flat=True))
    else:
        reels = Reel.objects.filter(
            author__profile__is_private=False
        ).select_related('author', 'author__profile').prefetch_related('likes', 'comments').order_by('-created_at')
        user_liked_reel_ids = set()
        user_saved_reel_ids = set()

    return render(request, 'posts/reels.html', {
        'reels': reels[:30],
        'user_liked_reel_ids': user_liked_reel_ids,
        'user_saved_reel_ids': user_saved_reel_ids,
        'comment_form': CommentForm(),
    })


@login_required
def create_reel_view(request):
    """Upload a new vertical short-form video reel with MIME and size verification."""
    if request.method == 'POST':
        form = ReelForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.author = request.user
            reel.save()
            messages.success(request, _("Your reel has been shared with the NIVO community!"))
            return redirect('posts:reels')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = ReelForm()

    return render(request, 'posts/upload_reel.html', {'form': form})


@login_required
def delete_reel_view(request, reel_id):
    """Delete own reel. Requires POST."""
    reel = get_object_or_404(Reel, pk=reel_id)
    if reel.author != request.user:
        return HttpResponseForbidden(_("You are not authorized to delete this reel."))

    if request.method == 'POST':
        reel.delete()
        messages.success(request, _("Reel deleted successfully."))
        return redirect('posts:reels')

    return redirect('posts:reels')


@login_required
def reel_like_toggle_view(request, reel_id):
    """Toggle like on a reel video. Enforces privacy permissions. Requires POST."""
    if request.method != 'POST':
        return redirect('posts:reels')

    reel = get_object_or_404(Reel, pk=reel_id)

    if not can_view_user_content(request.user, reel.author):
        return HttpResponseForbidden(_("Cannot like a private reel."))

    like_qs = ReelLike.objects.filter(reel=reel, user=request.user)

    if like_qs.exists():
        like_qs.delete()
        is_liked = False
    else:
        ReelLike.objects.create(reel=reel, user=request.user)
        is_liked = True
        create_notification(actor=request.user, recipient=reel.author, verb='reel_like', reel=reel)

    likes_count = reel.likes.count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_liked': is_liked,
            'likes_count': likes_count,
        })

    return redirect('posts:reels')


@login_required
def reel_save_toggle_view(request, reel_id):
    """Bookmark / save a reel. Requires POST."""
    if request.method != 'POST':
        return redirect('posts:reels')

    reel = get_object_or_404(Reel, pk=reel_id)

    if not can_view_user_content(request.user, reel.author):
        return HttpResponseForbidden(_("Cannot save a private reel."))

    save_qs = SavedReel.objects.filter(reel=reel, user=request.user)

    if save_qs.exists():
        save_qs.delete()
        is_saved = False
        message = _("Reel removed from saved.")
    else:
        SavedReel.objects.create(reel=reel, user=request.user)
        is_saved = True
        message = _("Reel saved to your collection!")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_saved': is_saved,
            'message': message,
        })

    messages.info(request, message)
    return redirect('posts:reels')


def record_reel_view(request, reel_id):
    """Increment reel view counter cleanly upon playback. Requires POST."""
    if request.method == 'POST':
        Reel.objects.filter(pk=reel_id).update(views_count=F('views_count') + 1)
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def reel_comment_view(request, reel_id):
    """Add comment to a reel video. Enforces privacy permissions. Requires POST."""
    if request.method != 'POST':
        return redirect('posts:reels')

    reel = get_object_or_404(Reel, pk=reel_id)

    if not can_view_user_content(request.user, reel.author):
        return HttpResponseForbidden(_("Cannot comment on a private reel."))

    form = CommentForm(request.POST)

    if form.is_valid():
        comment = ReelComment.objects.create(
            reel=reel,
            author=request.user,
            content=form.cleaned_data['content']
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            author_avatar = request.user.profile.get_avatar_url() or ''
            return JsonResponse({
                'status': 'ok',
                'author_username': request.user.username,
                'author_avatar': author_avatar,
                'content': comment.content,
                'comments_count': reel.comments.count(),
            })

    return redirect('posts:reels')


@login_required
def report_reel_view(request, reel_id):
    """Submit a report for a reel video."""
    reel = get_object_or_404(Reel, pk=reel_id)

    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reel = reel
            report.save()
            messages.success(request, _("Thank you. Your report has been submitted for review."))
            return redirect('posts:reels')
    else:
        form = ReportForm()

    return render(request, 'posts/report_post.html', {
        'form': form,
        'reel': reel
    })
