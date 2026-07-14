import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from payments.models import PaymentTransaction
from payments.forms import ReceiptUploadForm, RECEIPT_MAX_SIZE
from orders.models import Order
from products.models import Product
from accounts.models import CustomUser

TEMP_MEDIA = tempfile.mkdtemp(prefix="vulor-test-media-")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PaymentTransactionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="txuser@example.com", username="txuser", password="strongpass123"
        )
        self.product = Product.objects.create(
            name="Tx Product",
            description="desc",
            price=Decimal("1000.00"),
            category="hoodies",
            image=SimpleUploadedFile("p.jpg", b"x"),
            inventory_count=10,
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("1000.00"),
            shipping_address="1 St",
            shipping_city="Lagos",
            shipping_state="Lagos",
            customer_email="txuser@example.com",
        )

    def test_generate_reference_returns_unique_strings(self):
        ref1 = PaymentTransaction.generate_reference()
        ref2 = PaymentTransaction.generate_reference()
        self.assertIsInstance(ref1, str)
        self.assertNotEqual(ref1, ref2)

    def test_bank_transfer_fields_default_empty(self):
        tx = PaymentTransaction.objects.create(
            reference="ps-1",
            order=self.order,
            amount=Decimal("1200.00"),
        )
        self.assertEqual(tx.status, "pending")
        self.assertFalse(tx.receipt)
        self.assertEqual(tx.transaction_reference, "")
        self.assertIsNone(tx.submitted_at)


class ReceiptUploadFormTests(TestCase):
    def _form(self, filename="receipt.jpg", content=b"x", reference=""):
        return ReceiptUploadForm(
            data={"transaction_reference": reference},
            files={"receipt": SimpleUploadedFile(filename, content)},
        )

    def test_valid_image_receipt(self):
        form = self._form("receipt.jpg")
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_pdf_with_reference(self):
        form = self._form("receipt.pdf", reference="TRF/2026/0001")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["transaction_reference"], "TRF/2026/0001")

    def test_reference_is_optional(self):
        form = self._form("receipt.png")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["transaction_reference"], "")

    def test_rejects_disallowed_extension(self):
        form = self._form("receipt.exe")
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_rejects_oversized_file(self):
        form = self._form("receipt.jpg", content=b"x" * (RECEIPT_MAX_SIZE + 1))
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)

    def test_receipt_is_required(self):
        form = ReceiptUploadForm(data={"transaction_reference": "abc"}, files={})
        self.assertFalse(form.is_valid())
        self.assertIn("receipt", form.errors)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEMP_MEDIA,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    BANK_TRANSFER_BANK_NAME="GTBank",
    BANK_TRANSFER_ACCOUNT_NAME="VULOR Store",
    BANK_TRANSFER_ACCOUNT_NUMBER="0123456789",
)
class BankTransferFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="flow@example.com", username="flowuser", password="strongpass123"
        )
        self.client.force_login(self.user)
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("3000.00"),
            shipping_fee=Decimal("500.00"),
            shipping_address="1 Market St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="flow@example.com",
        )

    def _submit_receipt(self, filename="receipt.jpg", reference=""):
        return self.client.post(
            reverse("payments:submit_receipt", args=[self.order.id]),
            {
                "receipt": SimpleUploadedFile(filename, b"receipt-bytes"),
                "transaction_reference": reference,
            },
        )

    def test_instructions_page_shows_bank_details_and_creates_transaction(self):
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GTBank")
        self.assertContains(response, "0123456789")
        self.assertContains(response, self.order.order_number)
        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending")
        self.assertEqual(txn.amount, Decimal("3500.00"))

    def test_instructions_page_reuses_existing_pending_transaction(self):
        url = reverse("payments:transfer_instructions", args=[self.order.id])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(PaymentTransaction.objects.filter(order=self.order).count(), 1)

    @patch("services.email_service.ADMIN_EMAIL", "admin@vulor.test")
    def test_submit_receipt_marks_pending_verification_and_emails_admin(self):
        response = self._submit_receipt(reference="TRF-001")
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )

        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending_verification")

        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending_verification")
        self.assertTrue(txn.receipt)
        self.assertEqual(txn.transaction_reference, "TRF-001")
        self.assertIsNotNone(txn.submitted_at)

        admin_emails = [m for m in mail.outbox if "Verify payment" in m.subject]
        self.assertEqual(len(admin_emails), 1)
        self.assertEqual(admin_emails[0].to, ["admin@vulor.test"])
        self.assertEqual(len(admin_emails[0].attachments), 1)
        self.assertIn(self.order.order_number, admin_emails[0].body)

    def test_submit_invalid_receipt_keeps_order_pending(self):
        response = self._submit_receipt(filename="receipt.exe")
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "pending")
        txn = PaymentTransaction.objects.get(order=self.order)
        self.assertEqual(txn.status, "pending")

    def test_already_submitted_order_redirects_from_instructions(self):
        self._submit_receipt()
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertRedirects(
            response,
            reverse("orders:order_detail", args=[self.order.order_number]),
        )

    def test_other_users_order_is_not_accessible(self):
        other = CustomUser.objects.create_user(
            email="other@example.com", username="other", password="strongpass123"
        )
        self.client.force_login(other)
        response = self.client.get(
            reverse("payments:transfer_instructions", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_result_pages_render(self):
        for name in ("payment_success", "payment_failed"):
            response = self.client.get(reverse(f"payments:{name}", args=[self.order.id]))
            self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3500.00")  # failed page shows grand total


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    MEDIA_ROOT=TEMP_MEDIA,
)
class ReceiptAdminTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_superuser(
            email="root@example.com", username="root", password="strongpass123"
        )
        self.user = CustomUser.objects.create_user(
            email="rcpt@example.com", username="rcptuser", password="strongpass123"
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("3000.00"),
            shipping_address="1 Market St",
            shipping_city="Ikeja",
            shipping_state="Lagos",
            customer_email="rcpt@example.com",
        )
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            amount=Decimal("3000.00"),
            reference=PaymentTransaction.generate_reference(),
            status="pending_verification",
            receipt=SimpleUploadedFile("receipt.jpg", b"receipt-bytes"),
        )
        self.client.force_login(self.admin)

    def test_changelist_shows_view_and_download_links(self):
        response = self.client.get(reverse("admin:payments_paymenttransaction_changelist"))
        self.assertContains(response, self.txn.receipt.url)
        self.assertContains(response, "Download")

    def test_change_page_shows_receipt_preview(self):
        response = self.client.get(
            reverse("admin:payments_paymenttransaction_change", args=[self.txn.pk])
        )
        self.assertContains(response, f'<img src="{self.txn.receipt.url}"')
