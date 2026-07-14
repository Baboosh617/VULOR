from django.test import TestCase, RequestFactory
from django.urls import reverse
from accounts.models import CustomUser


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff = CustomUser.objects.create_user(
            email="admin@example.com",
            username="admin",
            password="strongpass123",
            is_staff=True,
        )

    def test_dashboard_home_url_resolves(self):
        self.assertEqual(reverse("dashboard:dashboard_home"), "/dashboard/")

    def test_dashboard_home_is_protected_from_anonymous(self):
        response = self.client.get(reverse("dashboard:dashboard_home"))
        self.assertNotEqual(response.status_code, 200)

    def test_dashboard_home_allowed_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:dashboard_home"))
        self.assertEqual(response.status_code, 200)


import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from orders.models import Order, OrderItem
from payments.models import PaymentTransaction
from products.models import Product

TEMP_MEDIA = tempfile.mkdtemp(prefix="vulor-test-media-")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEMP_MEDIA,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
)
class PaymentVerificationTests(TestCase):
    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            email="staff@example.com", username="staff", password="strongpass123", is_staff=True
        )
        self.customer = CustomUser.objects.create_user(
            email="cust@example.com", username="cust", password="strongpass123"
        )
        self.product = Product.objects.create(
            name="Verify Hoodie",
            description="desc",
            price=Decimal("3000.00"),
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=10,
        )
        self.order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("3000.00"),
            shipping_fee=Decimal("500.00"),
            shipping_address="1 Market St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="cust@example.com",
            payment_status="pending_verification",
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=2, price=Decimal("3000.00")
        )
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            amount=Decimal("3500.00"),
            reference=PaymentTransaction.generate_reference(),
            status="pending_verification",
            receipt=SimpleUploadedFile("receipt.jpg", b"receipt-bytes"),
        )
        self.client.force_login(self.staff)

    def test_confirm_payment_marks_paid_and_reduces_inventory(self):
        response = self.client.post(
            reverse("dashboard:confirm_payment", args=[self.order.id])
        )
        self.assertRedirects(response, reverse("dashboard:order_list"))

        self.order.refresh_from_db()
        self.txn.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.order.payment_status, "success")
        self.assertEqual(self.txn.status, "success")
        self.assertIsNotNone(self.txn.verified_at)
        self.assertTrue(self.order.inventory_adjusted)
        self.assertEqual(self.product.inventory_count, 8)

    def test_reject_payment_marks_failed(self):
        response = self.client.post(
            reverse("dashboard:reject_payment", args=[self.order.id])
        )
        self.assertRedirects(response, reverse("dashboard:order_list"))

        self.order.refresh_from_db()
        self.txn.refresh_from_db()

        self.assertEqual(self.order.payment_status, "failed")
        self.assertEqual(self.txn.status, "rejected")
        self.assertFalse(self.order.inventory_adjusted)

    def test_reject_requires_pending_verification(self):
        self.order.payment_status = "pending"
        self.order.save(update_fields=["payment_status"])
        self.client.post(reverse("dashboard:reject_payment", args=[self.order.id]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")

    def test_non_staff_cannot_confirm(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("dashboard:confirm_payment", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending_verification")

    def test_order_list_shows_verification_actions(self):
        response = self.client.get(reverse("dashboard:order_list"))
        self.assertContains(response, "Confirm Payment")
        self.assertContains(response, "View receipt")

    def test_reject_sends_customer_email(self):
        from django.core import mail
        mail.outbox.clear()
        self.client.post(reverse("dashboard:reject_payment", args=[self.order.id]))
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].to, ["cust@example.com"])
        self.assertIn(self.order.order_number, rejected[0].alternatives[0][0])
