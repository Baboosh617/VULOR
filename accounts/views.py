from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import CustomUserCreationForm, ContactForm, ProfileForm
from orders.models import Order
from django_ratelimit.decorators import ratelimit
from allauth.account.utils import complete_signup, setup_user_email
from allauth.account import app_settings as allauth_settings
from services.email_service import send_admin_contact_message

UserCreationForm = CustomUserCreationForm

@ratelimit(key='ip', rate='5/m', block=True)
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            setup_user_email(request, user, [])  # registers user.email as the primary EmailAddress
            return complete_signup(
                request, user, allauth_settings.EMAIL_VERIFICATION, reverse('home')
            )
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()

    return render(request, 'account/register.html', {'form': form, 'title': 'Sign Up'})

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect('profile_view')
    else:
        form = ProfileForm(instance=request.user)

    orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'account/profile.html', {'orders': orders, 'form': form})


@login_required
@require_POST
def deactivate_account(request):
    """Self-service account deactivation. Deliberately a soft-disable
    (is_active=False), never a hard delete — orders are financial records and
    must stay on file. Gated by a typed-email confirmation."""
    if request.POST.get('confirm', '').strip().lower() != request.user.email.lower():
        messages.error(request, "Type your email exactly to confirm deactivation.")
        return redirect('profile_view')

    user = request.user
    user.is_active = False
    user.save(update_fields=['is_active'])
    logout(request)
    messages.success(request, "Your account is deactivated. Your orders are kept on file.")
    return redirect('home')



def about(request):
    context = {
        'title': 'About VULOR'
    }
    return render(request, 'about.html', context)

@ratelimit(key='ip', rate='5/m', block=True)
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            send_admin_contact_message(
                full_name=cd['full_name'],
                email=cd['email'],
                subject=dict(ContactForm.SUBJECT_CHOICES)[cd['subject']],
                message=cd['message'],
            )
            messages.success(request, "Message sent. We'll get back to you within 24 hours.", extra_tags='contact')
            return redirect('contact')
        messages.error(request, 'Please correct the errors below and try again.', extra_tags='contact')
    else:
        form = ContactForm()

    context = {
        'title': 'Contact Us',
        'form': form,
    }
    return render(request, 'contact.html', context)

def size_guide(request):
    context = {
        'title': 'Size Guide'
    }
    return render(request, 'size_guide.html', context)