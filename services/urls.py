# services/urls.py
from django.urls import path
from django.http import HttpResponse
from .admin_report_service import send_weekly_sales_report, test_weekly_report

urlpatterns = [
    # ── Remove duplicate — keep only the proper view function ──
    path("test-weekly-report/", test_weekly_report, name="test_weekly_report"),
]