from django.test import TestCase
from decimal import Decimal
from payments.models import PaymentTransaction
from payments.forms import ReceiptUploadForm, RECEIPT_MAX_SIZE
from orders.models import Order
from products.models import Product
from accounts.models import CustomUser
from django.core.files.uploadedfile import SimpleUploadedFile


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
            paystack_reference="ps-1",
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
