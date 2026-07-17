from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
import logging

from dashboard.forms import CustomerForm

logger = logging.getLogger(__name__)
User = get_user_model()


@staff_member_required
def customer_list(request):
    users = User.objects.filter(is_superuser=False).order_by("-date_joined")
    query = request.GET.get("q")
    if query:
        users = users.filter(username__icontains=query)
    paginator = Paginator(users, 10)
    page_number = request.GET.get("page")
    users = paginator.get_page(page_number)
    return render(request, "dashboard/customers.html", {"users": users, "query": query})


@staff_member_required
def edit_customer(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, "Cannot modify superuser accounts here.")
        return redirect("dashboard:customer_list")
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            logger.info(f"User {user.username} updated by {request.user.username}.")
            messages.success(request, f"User {user.username} updated.")
            return redirect("dashboard:customer_list")
    else:
        form = CustomerForm(instance=user)
    return render(request, "dashboard/customer_form.html", {"form": form, "user": user})


@staff_member_required
@require_POST
def toggle_user_active(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.error(request, "Cannot modify superuser status.")
        return redirect("dashboard:customer_list")
    user.is_active = not user.is_active
    user.save()
    status = "activated" if user.is_active else "deactivated"
    logger.info(f"User {user.username} {status} by {request.user.username}.")
    messages.success(request, f"User {user.username} has been {status}.")
    return redirect("dashboard:customer_list")
