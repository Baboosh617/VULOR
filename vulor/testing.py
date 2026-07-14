"""Shared test infrastructure.

StoreTestCase carries the environment every integration test needs (in-memory
email, no rate limiting, throwaway media dir, plain static storage, fixed bank
details). The factories are the single source for order/transaction fixtures —
extend them here when models grow required fields.
"""
import tempfile
from decimal import Decimal

from django.test import TestCase, override_settings

TEMP_MEDIA = tempfile.mkdtemp(prefix="vulor-test-media-")

TEST_BANK = {
    "BANK_TRANSFER_BANK_NAME": "GTBank",
    "BANK_TRANSFER_ACCOUNT_NAME": "VULOR Store",
    "BANK_TRANSFER_ACCOUNT_NUMBER": "0123456789",
}


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEMP_MEDIA,
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage",
    **TEST_BANK,
)
class StoreTestCase(TestCase):
    """Base class for any test that creates orders, renders pages, or sends
    email. Order creation triggers a synchronous confirmation email, so the
    locmem backend is mandatory."""


def make_user(username="customer", **kwargs):
    from accounts.models import CustomUser

    kwargs.setdefault("email", f"{username}@example.com")
    kwargs.setdefault("password", "strongpass123")
    return CustomUser.objects.create_user(username=username, **kwargs)


def make_product(**kwargs):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from products.models import Product

    defaults = {
        "name": "Test Hoodie",
        "description": "desc",
        "price": Decimal("3000.00"),
        "category": "hoodies",
        "image": SimpleUploadedFile("p.jpg", b"x"),
        "inventory_count": 10,
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def make_order(user, **kwargs):
    from orders.models import Order

    defaults = {
        "total_amount": Decimal("3000.00"),
        "shipping_fee": Decimal("500.00"),
        "shipping_address": "1 Market St",
        "shipping_city": "Ikeja",
        "shipping_state": "Lagos",
        "customer_email": user.email,
    }
    defaults.update(kwargs)
    return Order.objects.create(user=user, **defaults)


def make_transaction(order, **kwargs):
    from payments.models import PaymentTransaction

    defaults = {
        "amount": order.grand_total,
        "reference": PaymentTransaction.generate_reference(),
        "status": "pending",
    }
    defaults.update(kwargs)
    return PaymentTransaction.objects.create(order=order, **defaults)
