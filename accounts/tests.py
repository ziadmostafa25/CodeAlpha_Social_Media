from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import Profile, Follow, Block
from accounts.permissions import can_view_user_content, is_user_blocked


class AccountsModelAndAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='userone', password='Password123!', email='u1@example.com')
        self.user2 = User.objects.create_user(username='usertwo', password='Password123!', email='u2@example.com')

    def test_profile_signal_creation(self):
        """User creation should automatically create corresponding Profile instance."""
        self.assertTrue(hasattr(self.user1, 'profile'))
        self.assertEqual(self.user1.profile.user, self.user1)
        self.assertEqual(self.user1.profile.get_display_name, 'userone')

    def test_user_registration(self):
        """Registering a new user creates user, hashes password, and creates profile."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'display_name': 'New Creator',
            'password': 'StrongPassword2026!',
            'confirm_password': 'StrongPassword2026!',
        })
        self.assertEqual(response.status_code, 302)
        new_u = User.objects.get(username='newuser')
        self.assertTrue(new_u.check_password('StrongPassword2026!'))
        self.assertEqual(new_u.profile.display_name, 'New Creator')

    def test_case_insensitive_registration(self):
        """Registering with case-variant of existing username fails."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'UserOne',  # existing is userone
            'email': 'another@example.com',
            'password': 'StrongPassword2026!',
            'confirm_password': 'StrongPassword2026!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'username', "A user with that username already exists (usernames are case-insensitive).")

    def test_user_login_and_logout(self):
        """Test authentication flow, including POST-only logout requirement."""
        login_res = self.client.post(reverse('accounts:login'), {
            'username': 'userone',
            'password': 'Password123!',
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user1.pk)

        # GET to logout should redirect without ending session
        get_logout_res = self.client.get(reverse('accounts:logout'))
        self.assertEqual(get_logout_res.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

        # POST to logout should end session
        post_logout_res = self.client.post(reverse('accounts:logout'))
        self.assertEqual(post_logout_res.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_safe_login_redirect(self):
        """Open redirect protection ensures user is only redirected to safe URLs."""
        # Malicious external redirect attempt
        bad_res = self.client.post(reverse('accounts:login') + '?next=https://malicious-phishing.com/steal', {
            'username': 'userone',
            'password': 'Password123!',
        })
        self.assertEqual(bad_res.status_code, 302)
        self.assertEqual(bad_res.url, reverse('posts:feed'))

        # Log out before next attempt
        self.client.logout()

        # Safe internal redirect
        safe_res = self.client.post(reverse('accounts:login') + '?next=/accounts/settings/profile/', {
            'username': 'userone',
            'password': 'Password123!',
        })
        self.assertEqual(safe_res.status_code, 302)
        self.assertEqual(safe_res.url, '/accounts/settings/profile/')

    def test_follow_and_unfollow(self):
        """Test follow/unfollow toggle and self-follow prevention."""
        self.client.login(username='userone', password='Password123!')

        # Follow user2
        res = self.client.post(reverse('accounts:follow_toggle', args=['usertwo']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['is_following'])
        self.assertTrue(Follow.objects.filter(follower=self.user1, following=self.user2).exists())

        # Unfollow user2
        res2 = self.client.post(reverse('accounts:follow_toggle', args=['usertwo']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.json()['is_following'])
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())

        # Self-follow prevention
        self_res = self.client.post(reverse('accounts:follow_toggle', args=['userone']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(self_res.status_code, 400)

    def test_private_account_request_and_acceptance(self):
        """Private accounts require follow approval before content is visible."""
        self.user2.profile.is_private = True
        self.user2.profile.save()

        # user1 cannot view user2's content initially
        self.assertFalse(can_view_user_content(self.user1, self.user2))

        # user1 requests to follow user2
        self.client.login(username='userone', password='Password123!')
        res = self.client.post(reverse('accounts:follow_toggle', args=['usertwo']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('is_pending'))
        self.assertFalse(data.get('is_following'))

        # Content is still private while request is pending
        self.assertFalse(can_view_user_content(self.user1, self.user2))

        # user2 accepts the follow request
        self.client.login(username='usertwo', password='Password123!')
        accept_res = self.client.post(reverse('accounts:accept_follow_request', args=['userone']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(accept_res.status_code, 200)

        # Now user1 can view user2's content
        self.assertTrue(can_view_user_content(self.user1, self.user2))

    def test_reject_follow_request(self):
        """User can reject incoming follow requests."""
        self.user2.profile.is_private = True
        self.user2.profile.save()
        Follow.objects.create(follower=self.user1, following=self.user2, is_accepted=False)

        self.client.login(username='usertwo', password='Password123!')
        reject_res = self.client.post(reverse('accounts:reject_follow_request', args=['userone']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(reject_res.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())

    def test_remove_follower(self):
        """User can remove an accepted follower."""
        Follow.objects.create(follower=self.user1, following=self.user2, is_accepted=True)
        self.client.login(username='usertwo', password='Password123!')
        rem_res = self.client.post(reverse('accounts:remove_follower', args=['userone']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(rem_res.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())

    def test_block_and_unblock_user(self):
        """Blocking severs follows and prevents viewing and messaging."""
        Follow.objects.create(follower=self.user1, following=self.user2, is_accepted=True)
        Follow.objects.create(follower=self.user2, following=self.user1, is_accepted=True)

        self.client.login(username='userone', password='Password123!')
        block_res = self.client.post(reverse('accounts:block_user', args=['usertwo']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(block_res.status_code, 200)
        self.assertTrue(block_res.json()['is_blocked'])

        # Both follows removed
        self.assertFalse(Follow.objects.filter(follower=self.user1, following=self.user2).exists())
        self.assertFalse(Follow.objects.filter(follower=self.user2, following=self.user1).exists())
        self.assertTrue(is_user_blocked(self.user1, self.user2))
        self.assertFalse(can_view_user_content(self.user1, self.user2))
        self.assertFalse(can_view_user_content(self.user2, self.user1))

        # Unblock user2
        unblock_res = self.client.post(reverse('accounts:unblock_user', args=['usertwo']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(unblock_res.status_code, 200)
        self.assertFalse(unblock_res.json()['is_blocked'])
        self.assertFalse(is_user_blocked(self.user1, self.user2))

    def test_delete_account_password_verification(self):
        """Account deletion requires correct current password verification."""
        self.client.login(username='userone', password='Password123!')

        # Incorrect password: stays on settings page via redirect, user remains intact
        wrong_res = self.client.post(reverse('settings:delete_account'), {'password': 'WrongPassword!'})
        self.assertEqual(wrong_res.status_code, 302)
        self.assertEqual(wrong_res.url, reverse('settings:delete_account'))
        self.assertTrue(User.objects.filter(username='userone').exists())

        # Correct password: deletes user and redirects to register
        correct_res = self.client.post(reverse('settings:delete_account'), {'password': 'Password123!'})
        self.assertEqual(correct_res.status_code, 302)
        self.assertEqual(correct_res.url, reverse('accounts:register'))
        self.assertFalse(User.objects.filter(username='userone').exists())

    def test_profile_update(self):
        """Authenticated user can update their display name, bio, and metadata."""
        self.client.login(username='userone', password='Password123!')
        res = self.client.post(reverse('accounts:edit_profile'), {
            'display_name': 'Updated Name',
            'bio': 'New updated bio statement.',
            'location': 'Cairo, Egypt',
            'website': 'https://example.com',
        })
        self.assertEqual(res.status_code, 302)
        self.user1.profile.refresh_from_db()
        self.assertEqual(self.user1.profile.display_name, 'Updated Name')
        self.assertEqual(self.user1.profile.location, 'Cairo, Egypt')

    def test_user_search(self):
        """Search query returns matching users."""
        res = self.client.get(reverse('accounts:search') + '?q=usertwo')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'usertwo')
