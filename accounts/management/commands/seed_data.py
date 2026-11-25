import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
import io

from accounts.models import Profile, Follow
from posts.models import Post, Comment, Like
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Seeds database with realistic demo creators, posts, comments, likes, and follows on NIVO.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding NIVO social media demonstration data..."))

        demo_users_data = [
            {
                'username': 'ziad_dev',
                'display_name': 'Ziad Mostafa',
                'email': 'ziad@example.com',
                'bio': 'Full Stack Engineer & UI/UX Craftsman. Building high-performance web applications with Python, Django, and modern web standards.',
                'location': 'Cairo, Egypt',
                'website': 'https://github.com',
                'color': (76, 29, 149),  # NIVO Deep Purple
            },
            {
                'username': 'sarah_design',
                'display_name': 'Sarah Jenkins',
                'email': 'sarah@example.com',
                'bio': 'Design systems lead & product architect. Obsessed with micro-interactions, typography, and dark mode aesthetics.',
                'location': 'San Francisco, CA',
                'website': 'https://dribbble.com',
                'color': (124, 58, 237),  # Electric Violet
            },
            {
                'username': 'omar_tech',
                'display_name': 'Omar Farouk',
                'email': 'omar@example.com',
                'bio': 'مهندس برمجيات وباحث في الذكاء الاصطناعي. شغوف بالأنظمة الموزعة وتطوير المنتجات الرقمية الحديثة على منصة نيفو.',
                'location': 'Alexandria, Egypt',
                'website': 'https://linkedin.com',
                'color': (16, 185, 129),  # Emerald
            },
            {
                'username': 'layla_art',
                'display_name': 'Layla Nour',
                'email': 'layla@example.com',
                'bio': 'Digital illustrator & 3D artist. Sharing color studies, process sketches, and creative workflows.',
                'location': 'Dubai, UAE',
                'website': 'https://behance.net',
                'color': (245, 158, 11),  # Amber
            },
            {
                'username': 'marcus_travel',
                'display_name': 'Marcus Vance',
                'email': 'marcus@example.com',
                'bio': 'Adventure photographer and storyteller. Documenting remote landscapes, mountain trails, and natural wonders.',
                'location': 'Reykjavik, Iceland',
                'website': 'https://unsplash.com',
                'color': (6, 182, 212),  # Cyan
            },
        ]

        created_users = {}

        # 1. Create Users & Profiles
        for data in demo_users_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['display_name'].split()[0],
                    'last_name': ' '.join(data['display_name'].split()[1:]),
                }
            )
            user.set_password('NivoDemo2026!')
            user.save()

            profile = user.profile
            profile.display_name = data['display_name']
            profile.bio = data['bio']
            profile.location = data['location']
            profile.website = data['website']

            # Generate aesthetic circular avatar image with initials
            avatar_img = self.create_avatar_image(data['display_name'], data['color'])
            avatar_filename = f"avatar_{data['username']}.png"
            profile.avatar.save(avatar_filename, ContentFile(avatar_img), save=True)

            created_users[data['username']] = user
            self.stdout.write(f"  [OK] User created/updated: @{user.username}")

        # 2. Establish Follow Networks
        follow_pairs = [
            ('ziad_dev', 'sarah_design'),
            ('ziad_dev', 'omar_tech'),
            ('ziad_dev', 'layla_art'),
            ('sarah_design', 'ziad_dev'),
            ('sarah_design', 'omar_tech'),
            ('omar_tech', 'ziad_dev'),
            ('omar_tech', 'marcus_travel'),
            ('layla_art', 'sarah_design'),
            ('layla_art', 'marcus_travel'),
            ('marcus_travel', 'ziad_dev'),
            ('marcus_travel', 'layla_art'),
        ]

        for follower_uname, following_uname in follow_pairs:
            u_follower = created_users[follower_uname]
            u_following = created_users[following_uname]
            Follow.objects.get_or_create(follower=u_follower, following=u_following)

        self.stdout.write("  [OK] Follow network established.")

        # 3. Create Posts
        posts_data = [
            {
                'author': 'ziad_dev',
                'content': "🚀 Exciting milestone! Just completed the full architecture for NIVO — an ultra-responsive social media platform built exclusively with Python, Django 6.1, and Vanilla JavaScript. Features bi-directional Arabic/English localization, seamless theme switching, and real-time interactions! #Python #Django #WebDev #Portfolio",
                'image_title': "NIVO Architecture & System Design",
                'image_gradient': ((204, 255, 0), (76, 29, 149)),
            },
            {
                'author': 'sarah_design',
                'content': "Design systems aren't just style guides; they are shared vocabulary between designers and engineers. Today we finalized the NIVO semantic token palette: Neon Lime + Deep Purple for Dark and Light themes. Clean contrast, accessible ratios, zero theme flash! 🎨✨",
                'image_title': "NIVO Design Tokens & Theming",
                'image_gradient': ((124, 58, 237), (204, 255, 0)),
            },
            {
                'author': 'omar_tech',
                'content': "سعيد جداً بتجربة منصة نيفو (NIVO)! التصميم العربي بالكامل (RTL) سلس ومتقن، وسرعة الاستجابة مع بايثون ودجانجو استثنائية. خطوة ممتازة نحو منصات تواصل عربية حديثة وعالمية المستوى. 🌟",
                'image_title': "تجربة المستخدم واللغة العربية",
                'image_gradient': ((16, 185, 129), (5, 150, 105)),
            },
            {
                'author': 'marcus_travel',
                'content': "Captured the midnight sun along the glacial lagoons of southeastern Iceland. The silence out here is breathtaking. Nature remains the greatest canvas ever created. 🏔️❄️",
                'image_title': "Iceland Glacial Expeditions",
                'image_gradient': ((6, 182, 212), (37, 99, 235)),
            },
            {
                'author': 'layla_art',
                'content': "Work in progress: experimenting with dual-light illumination and volumetric color gradients. What do you think about the atmosphere in this study? Feedback welcome! 💜🖌️",
                'image_title': "Color Study: Dual Atmosphere",
                'image_gradient': ((245, 158, 11), (236, 72, 153)),
            },
            {
                'author': 'ziad_dev',
                'content': "Pro tip for junior developers: Never hesitate to build projects that push you beyond tutorials. Implementing real authentication, secure file uploads, database constraints, and bidirectional layouts teaches you more than a dozen passive video lectures. Keep coding!",
                'image_title': None,  # Pure text post
                'image_gradient': None,
            },
        ]

        created_posts = []
        for pdata in posts_data:
            post = Post.objects.create(
                author=created_users[pdata['author']],
                content=pdata['content']
            )

            if pdata['image_title']:
                card_img = self.create_media_card(pdata['image_title'], pdata['image_gradient'])
                img_filename = f"post_card_{post.id}.png"
                post.image.save(img_filename, ContentFile(card_img), save=True)

            created_posts.append(post)

        self.stdout.write(f"  [OK] Created {len(created_posts)} realistic posts with custom media.")

        # 4. Likes & Comments
        sample_interactions = [
            (created_posts[0], 'sarah_design', "Outstanding work Ziad! The typography hierarchy and dark theme integration are immaculate."),
            (created_posts[0], 'omar_tech', "كود منظم وهيكل بيانات رائع يا زياد! فخور بهذا الإنجاز التقني المميز."),
            (created_posts[0], 'marcus_travel', "Love seeing real software built with passion and precision. Great job!"),
            (created_posts[1], 'ziad_dev', "Couldn't agree more, Sarah! Semantic CSS variables make theme toggling feel completely native."),
            (created_posts[2], 'layla_art', "التصميم العربي رائع جداً ومريح للعين! بالتوفيق دائماً."),
            (created_posts[3], 'sarah_design', "The atmospheric depth in this shot is mindblowing, Marcus!"),
            (created_posts[4], 'ziad_dev', "The contrast between the warm highlights and deep shadows is stunning, Layla."),
        ]

        for post, commenter_uname, comment_text in sample_interactions:
            user = created_users[commenter_uname]
            # Like
            Like.objects.get_or_create(post=post, user=user)
            # Comment
            Comment.objects.create(post=post, author=user, content=comment_text)

        # Additional likes
        Like.objects.get_or_create(post=created_posts[0], user=created_users['layla_art'])
        Like.objects.get_or_create(post=created_posts[1], user=created_users['marcus_travel'])
        Like.objects.get_or_create(post=created_posts[3], user=created_users['omar_tech'])
        Like.objects.get_or_create(post=created_posts[5], user=created_users['sarah_design'])
        Like.objects.get_or_create(post=created_posts[5], user=created_users['omar_tech'])

        # 5. Realistic Notifications
        Notification.objects.get_or_create(
            recipient=created_users['ziad_dev'],
            actor=created_users['sarah_design'],
            verb='comment',
            post=created_posts[0],
            defaults={'is_read': False}
        )
        Notification.objects.get_or_create(
            recipient=created_users['ziad_dev'],
            actor=created_users['omar_tech'],
            verb='like',
            post=created_posts[0],
            defaults={'is_read': False}
        )
        Notification.objects.get_or_create(
            recipient=created_users['ziad_dev'],
            actor=created_users['marcus_travel'],
            verb='follow',
            defaults={'is_read': False}
        )

        self.stdout.write(self.style.SUCCESS("[OK] NIVO demonstration content successfully seeded!"))
        self.stdout.write(self.style.SUCCESS("Demo credentials: username: ziad_dev | password: NivoDemo2026!"))

    def create_avatar_image(self, name, bg_color):
        """Generate a clean, high-resolution circular avatar banner with initials."""
        size = (300, 300)
        img = Image.new('RGB', size, bg_color)
        draw = ImageDraw.Draw(img)

        # Draw decorative inner circle
        draw.ellipse([20, 20, 280, 280], outline=(255, 255, 255, 120), width=4)

        # Initials text
        initials = "".join([part[0].upper() for part in name.split()[:2]])
        
        # Draw initials centered using basic font
        try:
            font = ImageFont.load_default(size=90)
        except TypeError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), initials, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size[0] - w) / 2
        y = (size[1] - h) / 2 - 10
        draw.text((x, y), initials, fill=(255, 255, 255), font=font)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def create_media_card(self, title, gradient_colors):
        """Generate a modern social media artwork card."""
        width, height = 900, 520
        img = Image.new('RGB', (width, height), gradient_colors[0])
        draw = ImageDraw.Draw(img)

        # Draw gradient simulation
        c1, c2 = gradient_colors
        for y in range(height):
            ratio = y / height
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Modern geometric grid & accent lines
        draw.rectangle([40, 40, width - 40, height - 40], outline=(255, 255, 255, 60), width=2)
        draw.line([60, height - 100, width - 60, height - 100], fill=(255, 255, 255, 100), width=2)

        # Brand watermark
        try:
            brand_font = ImageFont.load_default(size=24)
            title_font = ImageFont.load_default(size=44)
        except TypeError:
            brand_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        draw.text((60, 60), "NIVO • CREATIVE SHOWCASE", fill=(255, 255, 255, 200), font=brand_font)

        # Title text
        draw.text((60, height / 2 - 30), title, fill=(255, 255, 255), font=title_font)
        draw.text((60, height - 80), "Shared on NIVO — Your World, In Sync.", fill=(255, 255, 255, 180), font=brand_font)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
