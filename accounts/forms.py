# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.core.validators import RegexValidator
from django_recaptcha.fields import ReCaptchaField
from allauth.socialaccount.forms import SignupForm


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full bg-black border border-[#333333] text-white px-4 py-3 '
                     'text-sm focus:outline-none focus:border-[#dc2626] transition-all duration-300 rounded',
            'placeholder': 'Enter your email'
        })
    )

    username = forms.CharField(
        validators=[
            RegexValidator(
                regex=r'^[\w.@+-]+$',
                message='Username may only contain letters, digits and @/./+/-/_ characters.'
            )
        ],
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-black border border-[#333333] text-white px-4 py-3 '
                     'text-sm focus:outline-none focus:border-[#dc2626] transition-all duration-300 rounded',
            'placeholder': 'Choose a username'
        })
    )

    captcha = ReCaptchaField()

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

    def try_save(self, request):
        """Required by django-allauth SignupView."""
        try:
            user = self.save()
            return user, None
        except Exception as e:
            return None, str(e)


class CustomSocialSignupForm(SignupForm):
    """
    Displayed when a user signs up via Google OAuth for the first time.
    Allauth expects this form to exist at settings.SOCIALACCOUNT_FORMS['signup'].
    """

    def save(self, request):
        user = super().save(request)
        return user