# NIVO — Master Project Implementation Plan
### CodeAlpha Full Stack Development Internship — Task 2

---

## 1. Executive Summary & Brand Identity
- **Brand Name**: **NIVO** (نيفو)
- **Main Tagline (English)**: *Your World, In Sync.*
- **Tagline (Arabic)**: *عالمك، بتواصل يجمعنا.*
- **Core Concept**: A high-performance, polished social networking platform uniting creators and communities through multimedia posts, vertical reels, 1-on-1 direct messaging with real voice audio recording, privacy controls, bilingual support (English LTR & Arabic RTL), and Dark/Light/System adaptive theming.
- **Visual Identity**:
  - **Color Tokens**:
    - Signature Lime: `#C8F31D` (primary CTA, active accents, brand highlights)
    - Deep Purple: `#302052` (brand depth, headers, contrast backgrounds)
    - Dark Charcoal: `#171A18` (dark mode surface and text foundation)
    - Soft White: `#F7F7F2` (light mode canvas)
    - Supporting Lavender: `#E9DFFF` (subtle borders and tags)
    - Secondary Purple: `#7545F5` (interactive hover states)
  - **Logo**: Recreated vector SVG flowing ribbon **N** symbol with rounded edges and multi-stop gradient fills.

---

## 2. Technology Stack Architecture
- **Backend Framework**: Python 3.14.7 + Django 6.1.1 (Exclusively Python/Django).
- **Frontend Architecture**: Semantic HTML5, CSS3 Custom Properties (Variables), Vanilla JavaScript (ES6+), Django Templates.
- **Database**: PostgreSQL (Production) + SQLite 3 (Zero-config local development).
- **Internationalization (i18n)**: Django gettext translation catalogues (`en` and `ar`), bidirectional layouts (`ltr` and `rtl`) powered by CSS logical properties (285 translated entries).
- **Theming**: System-aware Dark, Light, and System modes synchronized via `localStorage` with inline zero-flash script in `<head>`.
- **Audio & Media**: In-browser microphone audio capture via HTML5 `MediaRecorder` API; deep magic byte verification for images, videos, and voice recordings.

---

## 3. Database Schema Architecture

1. **`accounts` App**:
   - `User` (Django built-in `auth.models.User`)
   - `Profile`: OneToOne with `User`, avatar, display_name, bio, location, website, is_private, notification preferences.
   - `Follow`: `follower` (FK User), `following` (FK User), `is_accepted` (BooleanField for private account approvals), `created_at`. Unique constraint on `('follower', 'following')`.
   - `Block`: `blocker` (FK User), `blocked` (FK User), `created_at`. Unique constraint on `('blocker', 'blocked')`.

2. **`posts` App**:
   - `Post`: `author` (FK User), `content` (TextField), `image` (ImageField, optional), `views_count`, `created_at`, `updated_at`.
   - `Comment`: `post` (FK Post), `author` (FK User), `content` (TextField), `created_at`, `updated_at`.
   - `Like`: `post` (FK Post), `user` (FK User), `created_at`. Unique constraint on `('post', 'user')`.
   - `Repost`: `post` (FK Post), `user` (FK User), `created_at`. Unique constraint on `('post', 'user')`.
   - `SavedPost`: `post` (FK Post), `user` (FK User), `created_at`. Unique constraint on `('post', 'user')`.
   - `Reel`: `author` (FK User), `caption`, `video` (FileField), `sound_title`, `thumbnail`, `views_count`, `created_at`.
   - `ReelLike`: `reel` (FK Reel), `user` (FK User), `created_at`. Unique constraint on `('reel', 'user')`.
   - `SavedReel`: `reel` (FK Reel), `user` (FK User), `created_at`. Unique constraint on `('reel', 'user')`.
   - `Report`: `reporter` (FK User), `post` (FK Post, optional), `reel` (FK Reel, optional), `reason`, `details`, `created_at`.

3. **`chat` App**:
   - `Conversation`: `participants` (ManyToManyField User), `created_at`, `updated_at`.
   - `Message`: `conversation` (FK Conversation), `sender` (FK User), `content`, `attachment` (ImageField), `audio_file` (FileField), `audio_duration` (PositiveIntegerField), `reply_to` (FK self), `is_read`, `created_at`.
   - `MessageReaction`: `message` (FK Message), `user` (FK User), `emoji`, `created_at`. Unique constraint on `('message', 'user', 'emoji')`.

4. **`notifications` App**:
   - `Notification`: `recipient` (FK User), `actor` (FK User), `verb` (like, comment, follow, follow_request, follow_accepted, repost, message, reel_like), `post` (FK Post, optional), `reel` (FK Reel, optional), `is_read`, `created_at`.

---

## 4. Phase-by-Phase Execution Roadmap

- **Phase 1 — Project Inspection & Security Audit**: Audited existing code, identified private account loopholes, state-changing GET endpoints, calling UI simulations, and missing model constraints. *(Completed)*
- **Phase 2 — Database Models & Migrations**: Created `Block`, `SavedReel`, `MessageReaction`, updated `Message` with `audio_file` and `audio_duration`, updated `Reel` with `sound_title`, and generated zero-conflict migrations. *(Completed)*
- **Phase 3 — Permission Architecture & Security Enforcement**: Implemented `can_view_user_content`, `can_message_user`, `is_user_blocked`, safe redirect checks, POST-only constraints on logout/follow/block/deletion, and password verification for deletion. *(Completed)*
- **Phase 4 — Core App Refactoring & Bug Fixing**:
  - `accounts`: follow requests, accept/reject endpoints, remove follower, block/unblock, case-insensitive usernames. *(Completed)*
  - `posts`: private account feed exclusion, post detail 403 enforcement, private repost rejection, reel save/like/delete, MIME magic byte validation. *(Completed)*
  - `chat`: zero DB writes on GET, 1-on-1 thread deduplication, real voice audio recording via MediaRecorder, read-only polling, POST read-marking, emoji reactions. *(Completed)*
  - `notifications`: follow request/acceptance verbs, preference enforcement, error logging. *(Completed)*
- **Phase 5 — UI/UX, Vector Brand Redesign & Responsive Design**: Implemented official NIVO logo SVG, Dark/Light/System theme switch, official color tokens (`#C8F31D`, `#302052`, `#171A18`), honest calling modal, mobile bottom bar, and tooltips. *(Completed)*
- **Phase 6 — Internationalization (i18n & RTL)**: Added 30 new translation strings (285 total) to `locale/ar/LC_MESSAGES/django.po` and recompiled `django.mo`. *(Completed)*
- **Phase 7 — Automated Testing Suite Expansion**: Implemented 49 unit and integration tests across all 4 apps with 100% pass rate. *(Completed)*
- **Phase 8 — Final Documentation & Quality Assurance**: Updated `README.md`, `PROGRESS.md`, `PROJECT_PLAN.md`, `AUDIT_REPORT.md`, `HANDOFF.md`, `.env.example`. *(Completed)*
