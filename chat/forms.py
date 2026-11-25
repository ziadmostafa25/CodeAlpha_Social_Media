import os
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Message


class MessageForm(forms.ModelForm):
    """Form to compose and send messages, image attachments, or real voice audio messages."""
    audio_duration = forms.IntegerField(required=False, initial=0, widget=forms.HiddenInput())
    reply_to = forms.ModelChoiceField(queryset=Message.objects.all(), required=False, widget=forms.HiddenInput())

    class Meta:
        model = Message
        fields = ['content', 'attachment', 'audio_file', 'audio_duration', 'reply_to']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'chat-message-input',
                'placeholder': _('Type a message...'),
                'autocomplete': 'off',
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'chat-attachment-input',
                'id': 'id_attachment',
                'accept': 'image/*',
            }),
            'audio_file': forms.FileInput(attrs={
                'id': 'id_audio_file',
                'accept': 'audio/webm,audio/ogg,audio/mp4,audio/wav',
            }),
            'audio_duration': forms.HiddenInput(),
            'reply_to': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        attachment = cleaned_data.get('attachment')
        audio_file = cleaned_data.get('audio_file')

        if not content and not attachment and not audio_file:
            raise ValidationError(_("Message must contain text, an image, or a voice recording."))
        return cleaned_data

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment and hasattr(attachment, 'size'):
            if attachment.size > 10 * 1024 * 1024:
                raise ValidationError(_("Image attachment cannot exceed 10MB."))
            try:
                header = attachment.read(16)
                attachment.seek(0)
                is_valid_img = (
                    header.startswith(b'\xff\xd8\xff') or # JPEG
                    header.startswith(b'\x89PNG\r\n\x1a\n') or # PNG
                    header.startswith(b'GIF87a') or header.startswith(b'GIF89a') or # GIF
                    b'WEBP' in header or header.startswith(b'RIFF') # WEBP
                )
                if not is_valid_img:
                    raise ValidationError(_("Invalid image format. Allowed formats: JPG, PNG, GIF, WebP."))
            except ValidationError:
                raise
            except Exception:
                pass
        return attachment

    def clean_audio_file(self):
        audio_file = self.cleaned_data.get('audio_file')
        if audio_file and hasattr(audio_file, 'size'):
            if audio_file.size > 15 * 1024 * 1024:
                raise ValidationError(_("Voice message cannot exceed 15MB."))
            try:
                header = audio_file.read(32)
                audio_file.seek(0)
                # Verify valid audio magic signatures: WebM, Ogg, WAV, or MP4
                is_webm = header.startswith(b'\x1a\x45\xdf\xa3')
                is_ogg = header.startswith(b'OggS')
                is_wav = header.startswith(b'RIFF') and b'WAVE' in header
                is_mp4 = b'ftyp' in header
                if not (is_webm or is_ogg or is_wav or is_mp4):
                    raise ValidationError(_("Invalid audio format. Allowed: WebM, Ogg, WAV, MP4 audio."))
            except ValidationError:
                raise
            except Exception:
                pass
        return audio_file
