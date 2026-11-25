
from django import forms
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError

from PIL import Image

from .models import Message


class MessageForm(forms.ModelForm):

    class Meta:
        model = Message
        fields = [
            'content',
            'attachment',
            'audio_file',
            'audio_duration',
            'reply_to',
        ]
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 1,
                'placeholder': _('Type a message...'),
            }),
            'audio_duration': forms.HiddenInput(),
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '')

        if len(content) > 5000:
            raise ValidationError(
                _("Message cannot exceed 5000 characters.")
            )

        return content

    def clean_audio_duration(self):
        duration = self.cleaned_data.get('audio_duration')

        if duration is not None and duration < 0:
            raise ValidationError(
                _("Audio duration cannot be negative.")
            )

        return duration

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')

        if not attachment:
            return attachment

        if attachment.size > 10 * 1024 * 1024:
            raise ValidationError(
                _("Image size cannot exceed 10 MB.")
            )

        try:
            attachment.seek(0)

            image = Image.open(attachment)
            image_format = image.format
            image.verify()

            if image_format not in ('JPEG', 'PNG', 'GIF', 'WEBP'):
                raise ValidationError(
                    _("Unsupported image format.")
                )

            attachment.seek(0)

        except ValidationError:
            raise

        except Exception:
            raise ValidationError(
                _("Invalid image file.")
            )

        return attachment

    def clean_audio_file(self):
        audio = self.cleaned_data.get('audio_file')

        if not audio:
            return audio

        if audio.size > 15 * 1024 * 1024:
            raise ValidationError(
                _("Audio file size cannot exceed 15 MB.")
            )

        try:
            audio.seek(0)
            header = audio.read(16)
            audio.seek(0)

            valid_audio = (
                header.startswith(b'\x1a\x45\xdf\xa3') or
                header.startswith(b'OggS') or
                header.startswith(b'RIFF') or
                (len(header) >= 8 and header[4:8] == b'ftyp')
            )

            if not valid_audio:
                raise ValidationError(
                    _("Unsupported or invalid audio file.")
                )

        except ValidationError:
            raise

        except Exception:
            raise ValidationError(
                _("Could not validate audio file.")
            )

        return audio
