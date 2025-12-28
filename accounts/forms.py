from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from django.core.validators import RegexValidator

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500',
            'placeholder': 'Enter your email'
        })
    )
    
    username = forms.CharField(
        validators=[RegexValidator(regex=r'^[\w.@+-]+$', message='Username may contain only letters, digits and @/./+/-/_ characters.')],
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500',
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
    
    # ADD THIS METHOD - fixes the 'try_save' error
    def try_save(self, request):
        """
        Required by django-allauth's SignupView in production
        """
        try:
            user = self.save()
            return user, None  # Return user and no error
        except Exception as e:
            return None, str(e)
