import re
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Profile


def validate_username_format(username):
    """Validate that username contains only letters, numbers, underscores, and periods."""
    if not re.match(r'^[a-zA-Z0-9_.]+$', username):
        raise ValidationError(_("Username can only contain letters, numbers, underscores, and periods."))
    if len(username) < 3:
        raise ValidationError(_("Username must be at least 3 characters long."))
    if len(username) > 30:
        raise ValidationError(_("Username cannot exceed 30 characters."))


class UserRegistrationForm(forms.ModelForm):
    """Registration form with case-insensitive username validation, email, and password."""
    display_name = forms.CharField(
        max_length=100,
        required=False,
        label=_("Display Name"),
        widget=forms.TextInput(attrs={'placeholder': _('e.g. Alex Morgan'), 'class': 'form-input'})
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'placeholder': _('Choose a secure password'), 'class': 'form-input'}),
        min_length=6
    )
    confirm_password = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={'placeholder': _('Repeat password'), 'class': 'form-input'}),
        min_length=6
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': _('Choose a unique username'), 'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'placeholder': _('you@example.com'), 'class': 'form-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        validate_username_format(username)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(_("A user with that username already exists (usernames are case-insensitive)."))
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', _("Passwords do not match."))
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            display_name = self.cleaned_data.get('display_name')
            if display_name:
                user.profile.display_name = display_name
                user.profile.save()
        return user


class UserLoginForm(AuthenticationForm):
    """Login form supporting styled inputs."""
    username = forms.CharField(
        label=_("Username"),
        widget=forms.TextInput(attrs={'placeholder': _('Username'), 'class': 'form-input', 'autofocus': True})
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'placeholder': _('Password'), 'class': 'form-input'})
    )


class ProfileUpdateForm(forms.ModelForm):
    """Form to update profile details: avatar, cover banner, display name, bio, location, and website."""
    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'avatar', 'cover_image', 'location', 'website']
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('Your full name')}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': _('Tell the community about yourself...')}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': _('e.g. Cairo, Egypt')}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'avatar': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'size'):
            if avatar.size > 5 * 1024 * 1024:  # 5 MB
                raise ValidationError(_("Avatar image size must be under 5MB."))
        return avatar

    def clean_cover_image(self):
        cover = self.cleaned_data.get('cover_image')
        if cover and hasattr(cover, 'size'):
            if cover.size > 8 * 1024 * 1024:  # 8 MB
                raise ValidationError(_("Cover image size must be under 8MB."))
        return cover


class AccountSettingsForm(forms.Form):
    """Form to manage account email and unique username."""
    username = forms.CharField(
        label=_("Username"),
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    email = forms.EmailField(
        label=_("Email Address"),
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )

    def __init__(self, current_user, *args, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        validate_username_format(username)
        # Check case-insensitive uniqueness against OTHER users
        if User.objects.filter(username__iexact=username).exclude(id=self.current_user.id).exists():
            raise ValidationError(_("This username is already taken by another account."))
        return username


class PrivacySettingsForm(forms.ModelForm):
    """Form to manage account visibility and messaging permissions."""
    class Meta:
        model = Profile
        fields = ['is_private', 'allow_messages_from']
        widgets = {
            'is_private': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'allow_messages_from': forms.Select(attrs={'class': 'form-input'}),
        }


class NotificationSettingsForm(forms.ModelForm):
    """Form to manage notification preferences."""
    class Meta:
        model = Profile
        fields = ['notify_likes', 'notify_comments', 'notify_follows', 'notify_messages', 'notify_reposts']
        widgets = {
            'notify_likes': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_comments': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_follows': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_messages': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_reposts': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
