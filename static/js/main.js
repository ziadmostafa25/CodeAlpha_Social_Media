/**
 * NIVO — Core JavaScript Application
 * Handles Theme Toggling, Language Switching, AJAX Likes, Follows,
 * Image Previews, Comment Submission, and Interactive Components.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLikeButtons();
  initFollowButtons();
  initImagePreview();
  initCommentForms();
  initDropdowns();
  initAlertDismissal();
});

/* ==========================================================================
   1. THEME SWITCHING (DARK / LIGHT / SYSTEM)
   ========================================================================== */
function initTheme() {
  const themeToggleBtns = document.querySelectorAll('.theme-toggle-btn');
  const storedTheme = localStorage.getItem('nivo-theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const currentTheme = storedTheme || (prefersDark ? 'dark' : 'light');

  applyTheme(currentTheme);

  themeToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const activeTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
      applyTheme(newTheme);
      localStorage.setItem('nivo-theme', newTheme);
    });
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const themeIcons = document.querySelectorAll('.theme-icon-container');

  themeIcons.forEach(container => {
    if (theme === 'dark') {
      // Show Sun icon (to switch to light)
      container.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      `;
    } else {
      // Show Moon icon (to switch to dark)
      container.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      `;
    }
  });
}

/* ==========================================================================
   2. CSRF TOKEN HELPER
   ========================================================================== */
function getCsrfToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  
  if (cookieValue) return cookieValue;

  const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
  return csrfInput ? csrfInput.value : '';
}

/* ==========================================================================
   3. AJAX LIKE / UNLIKE
   ========================================================================== */
function initLikeButtons() {
  document.addEventListener('click', async (e) => {
    const likeBtn = e.target.closest('.like-toggle-btn');
    if (!likeBtn) return;

    e.preventDefault();
    const postId = likeBtn.dataset.postId;
    const countSpan = likeBtn.querySelector('.like-count');
    const heartSvg = likeBtn.querySelector('svg');

    try {
      const response = await fetch(`/post/${postId}/like/`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          if (data.is_liked) {
            likeBtn.classList.add('liked');
            if (heartSvg) heartSvg.classList.add('pulse-animation');
            setTimeout(() => heartSvg && heartSvg.classList.remove('pulse-animation'), 400);
          } else {
            likeBtn.classList.remove('liked');
          }
          if (countSpan) {
            countSpan.textContent = data.likes_count;
          }
        }
      }
    } catch (err) {
      console.error('Like error:', err);
    }
  });
}

/* ==========================================================================
   4. AJAX FOLLOW / UNFOLLOW
   ========================================================================== */
function initFollowButtons() {
  document.addEventListener('click', async (e) => {
    const followBtn = e.target.closest('.follow-toggle-btn');
    if (!followBtn) return;

    e.preventDefault();
    const username = followBtn.dataset.username;
    const countTarget = document.querySelector(`[data-follower-count-for="${username}"]`);

    try {
      const response = await fetch(`/accounts/user/${username}/follow/`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          const isRTL = document.documentElement.getAttribute('dir') === 'rtl';
          if (data.is_following) {
            followBtn.classList.remove('btn-primary');
            followBtn.classList.add('btn-secondary');
            followBtn.textContent = isRTL ? 'إلغاء المتابعة' : 'Following';
          } else {
            followBtn.classList.remove('btn-secondary');
            followBtn.classList.add('btn-primary');
            followBtn.textContent = isRTL ? 'متابعة' : 'Follow';
          }

          if (countTarget) {
            countTarget.textContent = data.followers_count;
          }
        }
      }
    } catch (err) {
      console.error('Follow error:', err);
    }
  });
}

/* ==========================================================================
   5. IMAGE UPLOAD PREVIEW
   ========================================================================== */
function initImagePreview() {
  const imageInput = document.getElementById('post-image-input');
  const previewContainer = document.getElementById('image-preview-container');
  const previewImg = document.getElementById('image-preview-img');
  const removeBtn = document.getElementById('remove-preview-btn');

  if (!imageInput || !previewContainer || !previewImg) return;

  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewContainer.style.display = 'block';
      };
      reader.readAsDataURL(file);
    }
  });

  if (removeBtn) {
    removeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      imageInput.value = '';
      previewImg.src = '';
      previewContainer.style.display = 'none';
    });
  }
}

/* ==========================================================================
   6. AJAX COMMENT POSTING
   ========================================================================== */
function initCommentForms() {
  document.addEventListener('submit', async (e) => {
    const commentForm = e.target.closest('.ajax-comment-form');
    if (!commentForm) return;

    e.preventDefault();
    const postId = commentForm.dataset.postId;
    const inputField = commentForm.querySelector('.comment-input-field');
    const content = inputField ? inputField.value.trim() : '';

    if (!content) return;

    const formData = new FormData(commentForm);

    try {
      const response = await fetch(`/post/${postId}/comment/`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          // Clear input
          inputField.value = '';

          // Find comments container
          const commentsList = document.getElementById(`comments-list-${postId}`);
          if (commentsList) {
            const avatarHtml = data.author_avatar 
              ? `<img src="${data.author_avatar}" alt="${data.author_display_name}" class="comment-avatar">`
              : `<div class="comment-avatar avatar-initials">${data.author_username.charAt(0).toUpperCase()}</div>`;

            const newComment = document.createElement('div');
            newComment.className = 'comment-item';
            newComment.id = `comment-${data.comment_id}`;
            newComment.innerHTML = `
              ${avatarHtml}
              <div class="comment-bubble">
                <div class="comment-meta">
                  <span class="comment-author-name">@${data.author_username}</span>
                  <span class="comment-time">${data.created_at}</span>
                </div>
                <div class="comment-text">${escapeHtml(data.content)}</div>
              </div>
            `;
            commentsList.appendChild(newComment);
          }

          // Update comment count
          const countSpan = document.querySelector(`[data-comment-count-for="${postId}"]`);
          if (countSpan) {
            countSpan.textContent = data.comments_count;
          }
        }
      }
    } catch (err) {
      console.error('Comment error:', err);
    }
  });
}

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

/* ==========================================================================
   7. DROPDOWNS & MENUS
   ========================================================================== */
function initDropdowns() {
  document.addEventListener('click', (e) => {
    // Menu toggles
    const toggleBtn = e.target.closest('.post-menu-btn');
    if (toggleBtn) {
      e.stopPropagation();
      const dropdown = toggleBtn.nextElementSibling;
      // Close other open dropdowns
      document.querySelectorAll('.post-dropdown.show').forEach(d => {
        if (d !== dropdown) d.classList.remove('show');
      });
      if (dropdown) dropdown.classList.toggle('show');
      return;
    }

    // Close on click outside
    document.querySelectorAll('.post-dropdown.show').forEach(d => {
      d.classList.remove('show');
    });
  });
}

/* ==========================================================================
   8. ALERT DISMISSAL
   ========================================================================== */
function initAlertDismissal() {
  document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('.alert-close');
    if (!closeBtn) return;
    const alert = closeBtn.closest('.alert');
    if (alert) {
      alert.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-6px)';
      setTimeout(() => alert.remove(), 250);
    }
  });
}
