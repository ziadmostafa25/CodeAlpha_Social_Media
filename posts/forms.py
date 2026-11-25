import os
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Post, Comment, Reel, Report


class PostForm(forms.ModelForm):
    """Form for creating and editing posts with content and optional image."""
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'post-input-textarea',
                'rows': 3,
                'placeholder': _("What's on your mind? Share your story, thoughts, or creative work...")
            }),
            'image': forms.FileInput(attrs={
                'class': 'file-input-hidden',
                'id': 'post-image-input',
                'accept': 'image/*'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        image = cleaned_data.get('image')

        if not content and not image:
            raise ValidationError(_("A post must contain either text content or an image."))
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            if image.size > 10 * 1024 * 1024:  # 10 MB limit
                raise ValidationError(_("Image file size cannot exceed 10MB."))
            # Verify magic bytes for image
            try:
                header = image.read(16)
                image.seek(0)
                is_jpeg = header.startswith(b'\xff\xd8\xff')
                is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
                is_gif = header.startswith(b'GIF87a') or header.startswith(b'GIF89a')
                is_webp = b'WEBP' in header or header.startswith(b'RIFF')
                if not (is_jpeg or is_png or is_gif or is_webp):
                    raise ValidationError(_("Invalid image file format. Supported formats: JPEG, PNG, GIF, WebP."))
            except ValidationError:
                raise
            except Exception:
                pass
        return image


class CommentForm(forms.ModelForm):
    """Form for submitting a comment on a post."""
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'comment-input-field',
                'placeholder': _('Write a thoughtful comment...'),
                'autocomplete': 'off'
            }),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise ValidationError(_("Comment cannot be empty."))
        return content


class ReelForm(forms.ModelForm):
    """Form for uploading vertical short-form video reels."""
    class Meta:
        model = Reel
        fields = ['video', 'caption', 'sound_title', 'thumbnail']
        widgets = {
            'caption': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': _('Write a caption for your reel... #nivo #creators')
            }),
            'sound_title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': _('e.g. Original Sound — @username')
            }),
            'video': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'video/mp4,video/webm,video/quicktime'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
        }

    def clean_video(self):
        video = self.cleaned_data.get('video')
        if not video:
            raise ValidationError(_("Please select a video file."))

        # Validate file extension
        ext = os.path.splitext(video.name)[1].lower()
        if ext not in ['.mp4', '.webm', '.mov']:
            raise ValidationError(_("Unsupported video format. Please upload an MP4, WebM, or MOV video."))

        # 50MB file size limit for reels
        if hasattr(video, 'size') and video.size > 50 * 1024 * 1024:
            raise ValidationError(_("Video file size cannot exceed 50MB."))

        # Deep magic byte / content verification
        try:
            header = video.read(64)
            video.seek(0)
            is_webm = header.startswith(b'\x1a\x45\xdf\xa3')
            is_mp4_mov = b'ftyp' in header or b'moov' in header or b'mdat' in header or header[4:8] == b'ftyp'
            if not (is_webm or is_mp4_mov):
                raise ValidationError(_("Invalid or corrupted video file. Supported formats: MP4, WebM, MOV."))
        except ValidationError:
            raise
        except Exception:
            pass

        return video


class ReportForm(forms.ModelForm):
    """Form for submitting a report for moderation."""
    class Meta:
        model = Report
        fields = ['reason', 'details']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-input'}),
            'details': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': _('Provide additional context for our moderation team...')
            }),
        }
