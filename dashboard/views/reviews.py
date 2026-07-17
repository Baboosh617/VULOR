from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
import logging

from products.models import Review

logger = logging.getLogger(__name__)


@staff_member_required
def review_list(request):
    reviews = Review.objects.filter(approved=False).order_by("-created_at")
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get("page")
    reviews = paginator.get_page(page_number)
    return render(request, "dashboard/reviews.html", {"reviews": reviews})


@staff_member_required
@require_POST
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    logger.info(f"Review {review.id} deleted by {request.user.username}")
    messages.success(request, "Review has been deleted.")
    return redirect("dashboard:review_list")


@staff_member_required
@require_POST
def approve_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.approved = True
    review.approved_by = request.user
    review.save(update_fields=['approved', 'approved_by'])
    logger.info(f"Review {review.id} approved by {request.user.username}")
    return redirect("dashboard:review_list")
