from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse

from .forms import (
    UserRegistrationForm, UserLoginForm, ProfileUpdateForm,
    AccountSettingsForm, PrivacySettingsForm, NotificationSettingsForm
)
from .models import Profile, Follow, Block
from .permissions import can_view_user_content, is_user_blocked
from notifications.utils import create_notification


def register_view(request):
    """Register a new user account with case-insensitive username check."""
    if request.user.is_authenticated:
        return redirect('posts:feed')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _("Welcome to NIVO! Your account has been created."))
            return redirect('posts:feed')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Log in existing user with validation and safe redirection."""
    if request.user.is_authenticated:
        return redirect('posts:feed')

    raw_next = request.GET.get('next') or request.POST.get('next') or ''
    # Enforce safe redirect destination
    if raw_next and url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()}):
        next_url = raw_next
    else:
        next_url = reverse('posts:feed')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, _("Welcome back, @%(username)s!") % {'username': user.username})
            return redirect(next_url)
        else:
            messages.error(request, _("Invalid username or password."))
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'next': next_url})


def logout_view(request):
    """Log out the current user safely. Requires POST for state change."""
    if request.method == 'POST':
        logout(request)
        messages.info(request, _("You have been logged out."))
        return redirect('accounts:login')
    # If accessed via GET, redirect back without changing state
    return redirect('posts:feed')


def profile_view(request, username):
    """
    Display user profile with tabs: Posts, Reels, Reposts, and Saved (for owner).
    Respects private account visibility and block relationships.
    """
    profile_user = get_object_or_404(User.objects.select_related('profile'), username__iexact=username)
    profile = profile_user.profile
    tab = request.GET.get('tab', 'posts')

    is_own_profile = request.user.is_authenticated and request.user == profile_user
    is_following = False
    is_pending = False
    is_blocked_by_viewer = False

    if request.user.is_authenticated and not is_own_profile:
        follow_rel = Follow.objects.filter(follower=request.user, following=profile_user).first()
        if follow_rel:
            is_following = follow_rel.is_accepted
            is_pending = not follow_rel.is_accepted

        is_blocked_by_viewer = Block.objects.filter(blocker=request.user, blocked=profile_user).exists()
        # If viewer is blocked by target user
        if Block.objects.filter(blocker=profile_user, blocked=request.user).exists():
            return render(request, 'accounts/profile.html', {
                'profile_user': profile_user,
                'profile': profile,
                'is_blocked': True,
                'can_view_content': False,
            })

    # Privacy gate using shared permission logic
    can_view = can_view_user_content(request.user, profile_user)

    posts = []
    reels = []
    reposts = []
    saved_posts = []

    if can_view:
        if tab == 'posts':
            posts = profile_user.posts.select_related(
                'author', 'author__profile'
            ).prefetch_related('likes', 'comments').all()
        elif tab == 'reels':
            reels = profile_user.reels.select_related(
                'author', 'author__profile'
            ).prefetch_related('likes', 'comments').all()
        elif tab == 'reposts':
            from posts.models import Repost
            reposts = Repost.objects.filter(user=profile_user).select_related(
                'post', 'post__author', 'post__author__profile'
            ).prefetch_related('post__likes', 'post__comments')
        elif tab == 'saved' and is_own_profile:
            from posts.models import SavedPost
            saved_posts = SavedPost.objects.filter(user=profile_user).select_related(
                'post', 'post__author', 'post__author__profile'
            ).prefetch_related('post__likes', 'post__comments')

    context = {
        'profile_user': profile_user,
        'profile': profile,
        'posts': posts,
        'reels': reels,
        'reposts': reposts,
        'saved_posts': saved_posts,
        'posts_count': profile_user.posts.count(),
        'followers_count': profile_user.followers_set.filter(is_accepted=True).count(),
        'following_count': profile_user.following_set.filter(is_accepted=True).count(),
        'reels_count': profile_user.reels.count(),
        'is_following': is_following,
        'is_pending': is_pending,
        'is_blocked_by_viewer': is_blocked_by_viewer,
        'is_own_profile': is_own_profile,
        'can_view_content': can_view,
        'active_tab': tab,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):
    """Direct shortcut to edit profile (delegates to settings profile)."""
    return settings_profile_view(request)


@login_required
def follow_toggle_view(request, username):
    """Toggle follow/unfollow/follow request for a given user. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    target_user = get_object_or_404(User, username__iexact=username)

    if target_user == request.user:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': _("You cannot follow yourself.")}, status=400)
        messages.warning(request, _("You cannot follow yourself."))
        return redirect('accounts:profile', username=username)

    if is_user_blocked(request.user, target_user):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': _("Cannot follow a blocked user.")}, status=400)
        messages.error(request, _("Cannot follow a blocked user."))
        return redirect('accounts:profile', username=username)

    follow_rel = Follow.objects.filter(follower=request.user, following=target_user).first()

    if follow_rel:
        # Unfollow or Cancel Request
        follow_rel.delete()
        is_following = False
        is_pending = False
        message = _("Unfollowed @%(username)s.") % {'username': target_user.username}
    else:
        # Check if target account is private
        is_private = hasattr(target_user, 'profile') and target_user.profile.is_private
        is_accepted = not is_private
        Follow.objects.create(follower=request.user, following=target_user, is_accepted=is_accepted)
        
        is_following = is_accepted
        is_pending = not is_accepted

        verb = 'follow' if is_accepted else 'follow_request'
        create_notification(actor=request.user, recipient=target_user, verb=verb)
        
        if is_accepted:
            message = _("You are now following @%(username)s.") % {'username': target_user.username}
        else:
            message = _("Follow request sent to @%(username)s.") % {'username': target_user.username}

    followers_count = target_user.followers_set.filter(is_accepted=True).count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'is_following': is_following,
            'is_pending': is_pending,
            'followers_count': followers_count,
            'message': message,
        })

    messages.info(request, message)
    return redirect(request.META.get('HTTP_REFERER') or 'accounts:profile', username=username)


@login_required
def accept_follow_request_view(request, username):
    """Accept a pending follow request from a user. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    requester = get_object_or_404(User, username__iexact=username)
    follow_rel = Follow.objects.filter(follower=requester, following=request.user, is_accepted=False).first()

    if follow_rel:
        follow_rel.is_accepted = True
        follow_rel.save()
        create_notification(actor=request.user, recipient=requester, verb='follow_accepted')
        msg = _("Accepted follow request from @%(username)s.") % {'username': requester.username}
        messages.success(request, msg)
    else:
        msg = _("No pending request found.")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'is_accepted': True, 'message': msg})

    return redirect(request.META.get('HTTP_REFERER') or 'notifications:list')


@login_required
def reject_follow_request_view(request, username):
    """Reject a pending follow request. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    requester = get_object_or_404(User, username__iexact=username)
    Follow.objects.filter(follower=requester, following=request.user, is_accepted=False).delete()
    msg = _("Declined follow request from @%(username)s.") % {'username': requester.username}
    messages.info(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'message': msg})

    return redirect(request.META.get('HTTP_REFERER') or 'notifications:list')


@login_required
def remove_follower_view(request, username):
    """Remove a user from your followers list. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    target_follower = get_object_or_404(User, username__iexact=username)
    Follow.objects.filter(follower=target_follower, following=request.user).delete()
    msg = _("Removed @%(username)s from your followers.") % {'username': target_follower.username}
    messages.info(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'message': msg})

    return redirect('accounts:followers', username=request.user.username)


@login_required
def block_user_view(request, username):
    """Block a user. Removes any mutual follow relationships. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    target_user = get_object_or_404(User, username__iexact=username)
    if target_user == request.user:
        msg = _("You cannot block yourself.")
        messages.warning(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        return redirect('accounts:profile', username=username)

    Block.objects.get_or_create(blocker=request.user, blocked=target_user)
    # Remove all follow relationships between both users
    Follow.objects.filter(
        Q(follower=request.user, following=target_user) | Q(follower=target_user, following=request.user)
    ).delete()

    msg = _("@%(username)s has been blocked.") % {'username': target_user.username}
    messages.info(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'is_blocked': True, 'message': msg})

    return redirect('accounts:profile', username=username)


@login_required
def unblock_user_view(request, username):
    """Unblock a previously blocked user. Requires POST."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    target_user = get_object_or_404(User, username__iexact=username)
    Block.objects.filter(blocker=request.user, blocked=target_user).delete()
    msg = _("@%(username)s has been unblocked.") % {'username': target_user.username}
    messages.info(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok', 'is_blocked': False, 'message': msg})

    return redirect('accounts:profile', username=username)


def followers_list_view(request, username):
    """Display the list of followers for a user, respecting private account permissions."""
    profile_user = get_object_or_404(User, username__iexact=username)
    if not can_view_user_content(request.user, profile_user):
        return HttpResponseForbidden(_("This account is private."))

    followers = Follow.objects.filter(
        following=profile_user,
        is_accepted=True
    ).select_related('follower', 'follower__profile')

    return render(request, 'accounts/user_list.html', {
        'profile_user': profile_user,
        'users_list': [f.follower for f in followers],
        'title': _("Followers"),
        'list_type': 'followers',
    })


def following_list_view(request, username):
    """Display the list of users a user is following, respecting private account permissions."""
    profile_user = get_object_or_404(User, username__iexact=username)
    if not can_view_user_content(request.user, profile_user):
        return HttpResponseForbidden(_("This account is private."))

    following = Follow.objects.filter(
        follower=profile_user,
        is_accepted=True
    ).select_related('following', 'following__profile')

    return render(request, 'accounts/user_list.html', {
        'profile_user': profile_user,
        'users_list': [f.following for f in following],
        'title': _("Following"),
        'list_type': 'following',
    })


def user_search_view(request):
    """Search users by username or display name."""
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        results = User.objects.filter(
            Q(username__icontains=query) | Q(profile__display_name__icontains=query)
        ).distinct().select_related('profile')[:30]

    return render(request, 'accounts/search.html', {
        'query': query,
        'results': results,
    })


# ==============================================================================
# SETTINGS SUITE VIEWS
# ==============================================================================

@login_required
def settings_account_view(request):
    """Manage username and email."""
    if request.method == 'POST':
        form = AccountSettingsForm(request.user, request.POST)
        if form.is_valid():
            new_username = form.cleaned_data['username']
            new_email = form.cleaned_data['email']

            request.user.username = new_username
            request.user.email = new_email
            request.user.save()

            messages.success(request, _("Account information updated successfully."))
            return redirect('settings:account')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AccountSettingsForm(request.user, initial={
            'username': request.user.username,
            'email': request.user.email,
        })

    return render(request, 'settings/account.html', {
        'form': form,
        'active_section': 'account'
    })


@login_required
def settings_profile_view(request):
    """Manage display name, bio, avatar, cover banner, location, and website."""
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profile updated successfully."))
            return redirect('settings:profile')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, 'settings/profile.html', {
        'form': form,
        'active_section': 'profile'
    })


@login_required
def settings_privacy_view(request):
    """Manage private account and messaging permissions."""
    profile = request.user.profile

    if request.method == 'POST':
        form = PrivacySettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Privacy preferences saved."))
            return redirect('settings:privacy')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = PrivacySettingsForm(instance=profile)

    return render(request, 'settings/privacy.html', {
        'form': form,
        'active_section': 'privacy'
    })


@login_required
def settings_notifications_view(request):
    """Manage notification toggles (likes, comments, follows, messages, reposts)."""
    profile = request.user.profile

    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, _("Notification settings saved."))
            return redirect('settings:notifications')
    else:
        form = NotificationSettingsForm(instance=profile)

    return render(request, 'settings/notifications.html', {
        'form': form,
        'active_section': 'notifications'
    })


@login_required
def settings_appearance_view(request):
    """Manage Theme: Light, Dark, System."""
    return render(request, 'settings/appearance.html', {
        'active_section': 'appearance'
    })


@login_required
def settings_language_view(request):
    """Manage Language: English, Arabic."""
    return render(request, 'settings/language.html', {
        'active_section': 'language'
    })


@login_required
def settings_security_view(request):
    """Password change and security information."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, _("Your password has been changed successfully."))
            return redirect('settings:security')
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'settings/security.html', {
        'form': form,
        'active_section': 'security'
    })


def settings_help_view(request):
    """Help center, FAQ, About NIVO, and community guidelines."""
    return render(request, 'settings/help.html', {
        'active_section': 'help'
    })


@login_required
def settings_delete_account_view(request):
    """Delete user account with strict server-side password verification."""
    if request.method == 'POST':
        password = request.POST.get('password', '')
        if not request.user.check_password(password):
            messages.error(request, _("Incorrect password. Account deletion was not completed."))
            return redirect('settings:delete_account')

        user = request.user
        logout(request)
        user.delete()
        messages.info(request, _("Your account has been deleted."))
        return redirect('accounts:register')

    return render(request, 'settings/delete_account.html', {
        'active_section': 'delete_account'
    })
