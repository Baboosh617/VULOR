from decimal import Decimal

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import CustomUser
from cart.models import Cart
from dashboard.forms import ProductForm
from orders.models import OrderItem
from vulor.testing import (
    StoreTestCase,
    make_order,
    make_product,
    make_test_image_bytes,
    make_transaction,
    make_user,
)


class DashboardAccessTests(StoreTestCase):
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


class PaymentVerificationTests(StoreTestCase):
    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.customer = make_user("cust")
        self.product = make_product(name="Verify Hoodie")
        self.order = make_order(self.customer, payment_status="pending_verification")
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=2, price=Decimal("3000.00")
        )
        self.txn = make_transaction(
            self.order,
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
        self.assertContains(response, "CONFIRM")
        self.assertContains(response, "VIEW RECEIPT")

    def test_reject_sends_customer_email(self):
        mail.outbox.clear()
        self.client.post(reverse("dashboard:reject_payment", args=[self.order.id]))
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].to, ["cust@example.com"])
        self.assertIn(self.order.order_number, rejected[0].alternatives[0][0])

    def test_reject_reason_reaches_customer_email(self):
        mail.outbox.clear()
        self.client.post(
            reverse("dashboard:reject_payment", args=[self.order.id]),
            {"rejection_reason": "Amount on the receipt is short by 500."},
        )
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertEqual(len(rejected), 1)
        self.assertIn("Amount on the receipt is short by 500.", rejected[0].alternatives[0][0])

    def test_reject_without_reason_omits_team_note(self):
        mail.outbox.clear()
        self.client.post(reverse("dashboard:reject_payment", args=[self.order.id]))
        rejected = [m for m in mail.outbox if "Payment Not Confirmed" in m.subject]
        self.assertNotIn("Note from our team", rejected[0].alternatives[0][0])


class CustomerEditPrivilegeEscalationTests(StoreTestCase):
    """Regression tests for the CustomerForm mass-assignment fix: a staff
    account must not be able to grant itself or anyone else is_staff via
    the general customer-edit form, and must not be able to modify a
    superuser account through it at all."""

    def setUp(self):
        self.staff = make_user("staff", is_staff=True)
        self.other_customer = make_user("plain_customer")
        self.superuser = make_user(
            "root", is_staff=True, is_superuser=True, email="root@example.com"
        )
        self.client.force_login(self.staff)

    def test_is_staff_cannot_be_granted_via_customer_edit_form(self):
        response = self.client.post(
            reverse("dashboard:edit_customer", args=[self.other_customer.id]),
            {
                "username": self.other_customer.username,
                "email": self.other_customer.email,
                "first_name": "",
                "last_name": "",
                "is_active": "on",
                "is_staff": "on",  # attacker-supplied field the form must ignore
            },
        )
        self.assertRedirects(response, reverse("dashboard:customer_list"))
        self.other_customer.refresh_from_db()
        self.assertFalse(self.other_customer.is_staff)

    def test_edit_customer_rejects_superuser_target(self):
        original_email = self.superuser.email
        response = self.client.post(
            reverse("dashboard:edit_customer", args=[self.superuser.id]),
            {
                "username": "hijacked",
                "email": "hijacked@example.com",
                "first_name": "",
                "last_name": "",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("dashboard:customer_list"))
        self.superuser.refresh_from_db()
        self.assertEqual(self.superuser.email, original_email)
        self.assertEqual(self.superuser.username, "root")

    def test_edit_customer_get_also_rejects_superuser_target(self):
        response = self.client.get(
            reverse("dashboard:edit_customer", args=[self.superuser.id])
        )
        self.assertRedirects(response, reverse("dashboard:customer_list"))


class OrderListQueryTests(StoreTestCase):
    """Regression test for the select_related('user') addition to
    dashboard order_list: query count must stay flat as the number of
    distinct customers on the page grows, not scale with it (each row
    reads order.user.username in both the desktop and mobile layouts)."""

    def setUp(self):
        self.staff = make_user("liststaff", is_staff=True)
        self.client.force_login(self.staff)
        # Pre-create the staff user's own cart for the same reason as the
        # order_history/order_detail tests — cart_context runs on every
        # page and would otherwise lazily create it on the first request.
        Cart.objects.create(user=self.staff)

    def test_order_list_query_count_flat_regardless_of_distinct_customers(self):
        make_order(make_user("cust1"))
        with CaptureQueriesContext(connection) as queries_one_customer:
            self.client.get(reverse("dashboard:order_list"))

        make_order(make_user("cust2"))
        make_order(make_user("cust3"))
        with CaptureQueriesContext(connection) as queries_three_customers:
            self.client.get(reverse("dashboard:order_list"))

        self.assertEqual(len(queries_one_customer), len(queries_three_customers))


class ProductFormImageValidationTests(TestCase):
    """Product.image is a models.ImageField, so Django's own
    forms.ImageField already verifies the upload is a genuinely decodable
    image (via Pillow, internally) before ProductForm.clean() ever runs —
    a spoofed content_type alone can't get a non-image file past it. This
    is a regression test for that existing protection, not new code (see
    the comment in ProductForm.clean() for why no custom check was added
    there, unlike payments.forms.ReceiptUploadForm)."""

    def _valid_data(self, **overrides):
        data = {
            "name": "Test Hoodie",
            "slug": "",
            "description": "A hoodie",
            "price": "3000.00",
            "category": "hoodies",
            "inventory_count": "5",
            "available_sizes": "S,M,L",
            "available_colors": "Black",
        }
        data.update(overrides)
        return data

    def test_valid_image_passes(self):
        image = SimpleUploadedFile(
            "hoodie.jpg", make_test_image_bytes(), content_type="image/jpeg"
        )
        form = ProductForm(data=self._valid_data(), files={"image": image})
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_image_bytes_with_spoofed_content_type_is_rejected(self):
        # content_type is client-supplied and easy to spoof — the bytes
        # themselves aren't a real image, so Django's built-in ImageField
        # validation must still reject this even though content_type claims
        # otherwise. Rejected at the field level, so the error lands on
        # 'image', not '__all__' — ProductForm.clean()'s own checks never
        # get a chance to run for this case.
        fake = SimpleUploadedFile(
            "hoodie.jpg", b"not actually an image", content_type="image/jpeg"
        )
        form = ProductForm(data=self._valid_data(), files={"image": fake})
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)
