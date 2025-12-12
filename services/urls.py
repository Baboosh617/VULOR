from services.admin_report_service import send_weekly_sales_report
from django.urls import path
from django.http import HttpResponse
from .admin_report_service import send_weekly_sales_report, test_weekly_report


urlpatterns = [
    path("test-weekly-report/", test_weekly_report, name="test_weekly_report"),
    path("test-weekly-report/", lambda request: (send_weekly_sales_report(), HttpResponse("Sent!"))[1]),
]
