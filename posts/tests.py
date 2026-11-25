from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from posts.models import Post, Comment, Like, Repost, SavedPost, Reel, ReelLike, SavedReel, Report
from accounts.models import Follow


class PostsFunctionalityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(username='postauthor', password='Password123!')
        self.other_user = User.objects.create_user(username='otheruser', password='Password123!')
        self.post = Post.objects.create(author=self.author, content='Initial test post message.')

    def test_post_creation(self):
        """Authenticated user can publish a post."""
        self.client.login(username='postauthor', password='Password123!')
        res = self.client.post(reverse('posts:create_post'), {
            'content': 'A brand new story on NIVO.'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Post.objects.filter(content='A brand new story on NIVO.').exists())

    def test_post_edit_authorization(self):
        """Author can edit post; other users get 403 Forbidden."""
        # Other user tries to edit
        self.client.login(username='otheruser', password='Password123!')
        res_forbidden = self.client.post(reverse('posts:edit_post', args=[self.post.id]), {
            'content': 'Malicious modification attempt'
        })
        self.assertEqual(res_forbidden.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, 'Initial test post message.')

        # Author edits post
        self.client.login(username='postauthor', password='Password123!')
        res_ok = self.client.post(reverse('posts:edit_post', args=[self.post.id]), {
            'content': 'Authorized updated content.'
        })
        self.assertEqual(res_ok.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, 'Authorized updated content.')

    def test_post_delete_authorization(self):
        """Author can delete post; others receive 403 Forbidden."""
        self.client.login(username='otheruser', password='Password123!')
        del_forbidden = self.client.post(reverse('posts:delete_post', args=[self.post.id]))
        self.assertEqual(del_forbidden.status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

        self.client.login(username='postauthor', password='Password123!')
        del_ok = self.client.post(reverse('posts:delete_post', args=[self.post.id]))
        self.assertEqual(del_ok.status_code, 302)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_like_and_unlike_toggle(self):
        """Toggle like creates and removes like without duplicate errors."""
        self.client.login(username='otheruser', password='Password123!')
        
        # Like
        res1 = self.client.post(reverse('posts:like_toggle', args=[self.post.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['is_liked'])
        self.assertEqual(res1.json()['likes_count'], 1)
        self.assertTrue(Like.objects.filter(post=self.post, user=self.other_user).exists())

        # Unlike
        res2 = self.client.post(reverse('posts:like_toggle', args=[self.post.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.json()['is_liked'])
        self.assertEqual(res2.json()['likes_count'], 0)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.other_user).exists())

    def test_comment_creation_and_deletion(self):
        """User can add comments and delete their own comment."""
        self.client.login(username='otheruser', password='Password123!')
        
        res = self.client.post(reverse('posts:add_comment', args=[self.post.id]), {
            'content': 'Great post!'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.post.comments.count(), 1)
        comment = self.post.comments.first()
        self.assertEqual(comment.content, 'Great post!')

        # Delete comment
        del_res = self.client.post(reverse('posts:delete_comment', args=[comment.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(self.post.comments.count(), 0)

    def test_feed_excludes_private_posts_for_non_followers(self):
        """Private accounts' posts are hidden from non-followers in feed."""
        self.author.profile.is_private = True
        self.author.profile.save()

        # Unauthenticated / non-follower view feed
        res = self.client.get(reverse('posts:feed'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'Initial test post message.')

        # Follower with accepted follow can see private post
        Follow.objects.create(follower=self.other_user, following=self.author, is_accepted=True)
        self.client.login(username='otheruser', password='Password123!')
        res_follower = self.client.get(reverse('posts:feed'))
        self.assertEqual(res_follower.status_code, 200)
        self.assertContains(res_follower, 'Initial test post message.')

    def test_post_detail_privacy_enforcement(self):
        """Direct access to private post returns 403 Forbidden for non-followers."""
        self.author.profile.is_private = True
        self.author.profile.save()

        # Unauthorized viewer
        self.client.login(username='otheruser', password='Password123!')
        forbidden_res = self.client.get(reverse('posts:post_detail', args=[self.post.id]))
        self.assertEqual(forbidden_res.status_code, 403)

        # Author can view
        self.client.login(username='postauthor', password='Password123!')
        author_res = self.client.get(reverse('posts:post_detail', args=[self.post.id]))
        self.assertEqual(author_res.status_code, 200)

    def test_repost_private_post_disallowed(self):
        """Posts from private accounts cannot be reposted."""
        self.author.profile.is_private = True
        self.author.profile.save()

        self.client.login(username='otheruser', password='Password123!')
        repost_res = self.client.post(reverse('posts:repost_toggle', args=[self.post.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(repost_res.status_code, 400)
        self.assertFalse(Repost.objects.filter(post=self.post, user=self.other_user).exists())

    def test_save_and_unsave_post_toggle(self):
        """User can save and bookmark posts to their private collection."""
        self.client.login(username='otheruser', password='Password123!')

        # Save post
        res_save = self.client.post(reverse('posts:save_toggle', args=[self.post.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_save.status_code, 200)
        self.assertTrue(res_save.json()['is_saved'])
        self.assertTrue(SavedPost.objects.filter(post=self.post, user=self.other_user).exists())

        # Unsave post
        res_unsave = self.client.post(reverse('posts:save_toggle', args=[self.post.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_unsave.status_code, 200)
        self.assertFalse(res_unsave.json()['is_saved'])
        self.assertFalse(SavedPost.objects.filter(post=self.post, user=self.other_user).exists())

    def test_saved_posts_view(self):
        """Saved posts list renders user's saved items."""
        SavedPost.objects.create(post=self.post, user=self.other_user)
        self.client.login(username='otheruser', password='Password123!')

        res = self.client.get(reverse('posts:saved_posts'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Initial test post message.')

    def test_reel_creation_and_feed(self):
        """User can upload valid video reel and view reels feed."""
        self.client.login(username='postauthor', password='Password123!')
        valid_video = SimpleUploadedFile(
            "reel_video.mp4",
            b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 100,
            content_type="video/mp4"
        )
        res = self.client.post(reverse('posts:create_reel'), {
            'caption': 'Creative vertical reel #viral',
            'sound_title': 'Original Sound — @postauthor',
            'video': valid_video,
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Reel.objects.filter(caption='Creative vertical reel #viral').exists())

        # View in reels feed
        feed_res = self.client.get(reverse('posts:reels'))
        self.assertEqual(feed_res.status_code, 200)
        self.assertContains(feed_res, 'Creative vertical reel #viral')

    def test_reel_invalid_file_rejected(self):
        """Invalid video file header fails validation."""
        self.client.login(username='postauthor', password='Password123!')
        fake_video = SimpleUploadedFile(
            "fake_clip.mp4",
            b"Not a real mp4 video file header",
            content_type="video/mp4"
        )
        res = self.client.post(reverse('posts:create_reel'), {
            'caption': 'Bad file reel',
            'video': fake_video,
        })
        self.assertEqual(res.status_code, 200)
        self.assertFormError(res.context['form'], 'video', "Invalid or corrupted video file. Supported formats: MP4, WebM, MOV.")

    def test_reel_like_and_save_toggle(self):
        """User can like and save reel videos."""
        reel = Reel.objects.create(
            author=self.author,
            caption='Reel to like and save',
            video=SimpleUploadedFile("dummy.mp4", b"\x00\x00\x00\x20ftypmp42" + b"\x00"*20, content_type="video/mp4")
        )
        self.client.login(username='otheruser', password='Password123!')

        # Like reel
        like_res = self.client.post(reverse('posts:reel_like', args=[reel.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(like_res.status_code, 200)
        self.assertTrue(like_res.json()['is_liked'])
        self.assertTrue(ReelLike.objects.filter(reel=reel, user=self.other_user).exists())

        # Save reel
        save_res = self.client.post(reverse('posts:reel_save', args=[reel.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(save_res.status_code, 200)
        self.assertTrue(save_res.json()['is_saved'])
        self.assertTrue(SavedReel.objects.filter(reel=reel, user=self.other_user).exists())

    def test_report_submission(self):
        """Users can submit moderation reports for posts."""
        self.client.login(username='otheruser', password='Password123!')
        res = self.client.post(reverse('posts:report_post', args=[self.post.id]), {
            'reason': 'spam',
            'details': 'Repetitive spam content.',
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Report.objects.filter(post=self.post, reporter=self.other_user, reason='spam').exists())

    def test_i18n_language_switching_and_rtl(self):
        """Test English and Arabic localization and RTL/LTR direction rendering."""
        # English feed view (default)
        en_res = self.client.get(reverse('posts:feed'))
        self.assertEqual(en_res.status_code, 200)
        self.assertContains(en_res, 'dir="ltr"')

        # Switch to Arabic via Django's set_language
        self.client.post(reverse('set_language'), {'language': 'ar'})
        ar_res = self.client.get(reverse('posts:feed'))
        self.assertEqual(ar_res.status_code, 200)
        self.assertContains(ar_res, 'dir="rtl"')
        self.assertContains(ar_res, 'الخلاصة')
