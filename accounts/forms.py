# accounts/forms.py
from django import forms
from allauth.account.forms import SignupForm as AllauthSignupForm

from .models import CustomUser


class SignupForm(AllauthSignupForm):
    """Two fields only — email + password. Allauth auto-generates the username
    (ACCOUNT_USERNAME_REQUIRED=False) and skips the confirm-password field
    (ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE=False); the register template renders
    the inputs by hand with the design system's classes."""


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