from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from orders.models import OrderItem
from services.tasks import send_weekly_sales_report_task
from vulor.testing import StoreTestCase, make_order, make_product, make_user


class WeeklyReportEndpointTests(StoreTestCase):
    """The debug 'test-weekly-report' endpoint was unauthenticated and
    side-effecting (sent a real email on every hit). It must not be
    reachable at all — regression test for its removal."""

    def test_test_weekly_report_url_no_longer_resolves(self):
        response = self.client.get("/services/test-weekly-report/")
        self.assertEqual(response.status_code, 404)

    def test_no_reverse_for_removed_route_name(self):
        with self.assertRaises(Exception):
            reverse("test_weekly_report")


class WeeklyReportTaskDedupTests(StoreTestCase):
    """send_weekly_sales_report_task used to reimplement the report's
    query/aggregation/email logic verbatim instead of calling the shared
    function — two copies that could silently drift. Regression tests that
    the task now delegates, and that the delegated call still produces the
    correct email end-to-end."""

    @patch("services.admin_report_service.send_weekly_sales_report")
    def test_task_delegates_to_shared_report_function(self, mock_report):
        # send_weekly_sales_report_task imports the function lazily inside
        # its own body (from services.admin_report_service import ...), so
        # the patch target is the source module, not services.tasks.
        send_weekly_sales_report_task()
        mock_report.assert_called_once_with()

    @override_settings(ADMIN_EMAIL="admin@vulor.test")
    def test_task_sends_correct_email_end_to_end(self):
        user = make_user("reportbuyer")
        product = make_product(name="Report Hoodie", inventory_count=10)
        order = make_order(user, total_amount=Decimal("2000.00"))
        OrderItem.objects.create(
            order=order, product=product, quantity=2, price=Decimal("1000.00")
        )

        mail.outbox.clear()
        send_weekly_sales_report_task()

        reports = [m for m in mail.outbox if "Weekly Sales Report" in m.subject]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].to, ["admin@vulor.test"])
        self.assertIn("Total Orders:</strong> 1", reports[0].alternatives[0][0])
