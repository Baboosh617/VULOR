from django.test import TestCase
from decimal import Decimal
from django.db import IntegrityError
from payments.models import Payment, PaymentTransaction
from orders.models import Order
from products.models import Product
from accounts.models import CustomUser
from django.core.files.uploadedfile import SimpleUploadedFile


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="payuser@example.com", username="payuser", password="strongpass123"
        )

    def test_amount_in_kobo(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("2500.00"),
            reference="ref-abc-123",
        )
        self.assertEqual(payment.amount_in_kobo, 250000)

    def test_reference_must_be_unique(self):
        Payment.objects.create(user=self.user, amount=Decimal("100.00"), reference="same-ref")
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                user=self.user, amount=Decimal("100.00"), reference="same-ref"
            )


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

    def test_amount_in_kobo(self):
        tx = PaymentTransaction.objects.create(
            paystack_reference="ps-1",
            order=self.order,
            amount=Decimal("1200.00"),
        )
        self.assertEqual(tx.amount_in_kobo, 120000)
