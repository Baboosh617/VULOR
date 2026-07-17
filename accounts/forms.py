# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.core.validators import RegexValidator
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


class ContactForm(forms.Form):
    """Fields match the contact.html template inputs (frontend/templates/contact.html)."""

    SUBJECT_CHOICES = [
        ('order_issue', 'Order issue'),
        ('delivery', 'Delivery'),
        ('product_question', 'Product question'),
        ('other', 'Other'),
    ]

    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    subject = forms.ChoiceField(choices=SUBJECT_CHOICES)
    message = forms.CharField(widget=forms.Textarea)


class ProfileForm(forms.ModelForm):
    """Editable account details on /accounts/profile/. Widget classes match the
    design system's form components so the fields render on-system."""

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "phone", "address"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "v-input", "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"class": "v-input", "autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={
                "class": "v-input", "inputmode": "tel", "autocomplete": "tel",
                "placeholder": "+234 800 000 0000",
            }),
            "address": forms.Textarea(attrs={
                "class": "v-textarea", "rows": 3, "autocomplete": "street-address",
                "placeholder": "STREET, CITY, STATE",
            }),
        }


class CustomSocialSignupForm(SignupForm):
    """
    Displayed when a user signs up via Google OAuth for the first time.
    Allauth expects this form to exist at settings.SOCIALACCOUNT_FORMS['signup'].
    """

    def save(self, request):
        user = super().save(request)
        return user