from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm
from orders.models import Order
from django_ratelimit.decorators import ratelimit

UserCreationForm = CustomUserCreationForm

@ratelimit(key='ip', rate='5/m', block=True)
def register(request):
    """Custom registration view that works with allauth"""
    print("REGISTER VIEW HIT", request.method)
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "Registration successful!")
            return redirect('home')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()
    
    # Pass additional context for template
    context = {
        'form': form,
        'title': 'Sign Up',
    }
    return render(request, 'account/register.html', context)

@login_required
def profile_view(request):
    # Get user's orders for the profile page
    orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]  # Last 5 orders
    
    context = {
        'orders': orders,
    }
    return render(request, 'account/profile.html', context)



def about(request):
    context = {
        'title': 'About VULOR'
    }
    return render(request, 'about.html', context)

def contact(request):
    context = {
        'title': 'Contact Us'
    }
    return render(request, 'contact.html', context)

def size_guide(request):
    context = {
        'title': 'Size Guide'
    }
    return render(request, 'size_guide.html', context)


@ratelimit(key='ip', rate='5/m', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'account/login.html')