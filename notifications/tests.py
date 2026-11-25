from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from posts.models import Post
from notifications.models import Notification
from notifications.utils import create_notification


class NotificationsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='usera', password='Password123!')
        self.user_b = User.objects.create_user(username='userb', password='Password123!')
        self.post = Post.objects.create(author=self.user_a, content='Post for notification test.')

    def test_notification_helper_dispatches(self):
        """Notification is created when actor != recipient."""
        notif = create_notification(actor=self.user_b, recipient=self.user_a, verb='like', post=self.post)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient, self.user_a)
        self.assertEqual(notif.actor, self.user_b)
        self.assertEqual(notif.verb, 'like')
        self.assertFalse(notif.is_read)

    def test_self_action_does_not_create_notification(self):
        """User interacting with their own post generates no notification."""
        notif = create_notification(actor=self.user_a, recipient=self.user_a, verb='like', post=self.post)
        self.assertIsNone(notif)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notifications_list_get_is_readonly(self):
        """GET request to notifications list never mutates read status in database."""
        notif = create_notification(actor=self.user_b, recipient=self.user_a, verb='follow')
        self.assertFalse(notif.is_read)

        self.client.login(username='usera', password='Password123!')
        res = self.client.get(reverse('notifications:list'))
        self.assertEqual(res.status_code, 200)

        notif.refresh_from_db()
        self.assertFalse(notif.is_read)

    def test_mark_single_notification_read(self):
        """Marking a single notification requires POST."""
        notif = create_notification(actor=self.user_b, recipient=self.user_a, verb='comment', post=self.post)
        self.client.login(username='usera', password='Password123!')

        # GET should not mark as read
        get_res = self.client.get(reverse('notifications:mark_read', args=[notif.id]))
        self.assertEqual(get_res.status_code, 302)
        notif.refresh_from_db()
        self.assertFalse(notif.is_read)

        # POST marks as read
        post_res = self.client.post(reverse('notifications:mark_read', args=[notif.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(post_res.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_all_read_view(self):
        """User can mark all unread notifications as read via POST."""
        create_notification(actor=self.user_b, recipient=self.user_a, verb='follow')
        create_notification(actor=self.user_b, recipient=self.user_a, verb='like', post=self.post)
        self.assertEqual(self.user_a.notifications.filter(is_read=False).count(), 2)

        self.client.login(username='usera', password='Password123!')
        res = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(self.user_a.notifications.filter(is_read=False).count(), 0)

    def test_notification_preference_opt_out(self):
        """When recipient opts out of specific notifications, no notification is created."""
        self.user_a.profile.notify_likes = False
        self.user_a.profile.save()

        notif = create_notification(actor=self.user_b, recipient=self.user_a, verb='like', post=self.post)
        self.assertIsNone(notif)
        self.assertEqual(self.user_a.notifications.count(), 0)

    def test_follow_request_and_accepted_notifications(self):
        """Follow request and follow acceptance notifications are created with appropriate verbs."""
        notif_req = create_notification(actor=self.user_b, recipient=self.user_a, verb='follow_request')
        self.assertIsNotNone(notif_req)
        self.assertEqual(notif_req.verb, 'follow_request')

        notif_acc = create_notification(actor=self.user_a, recipient=self.user_b, verb='follow_accepted')
        self.assertIsNotNone(notif_acc)
        self.assertEqual(notif_acc.verb, 'follow_accepted')
