from django.urls import reverse
from vulor.testing import StoreTestCase, make_user
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from accounts.models import CustomUser


class CustomUserModelTests(TestCase):
    def test_create_user_with_email(self):
        user = CustomUser.objects.create_user(
            email="buyer@example.com",
            username="buyer",
            password="strongpass123",
        )
        self.assertEqual(user.email, "buyer@example.com")
        self.assertTrue(user.check_password("strongpass123"))

    def test_email_is_username_field(self):
        self.assertEqual(CustomUser.USERNAME_FIELD, "email")
        self.assertIn("username", CustomUser.REQUIRED_FIELDS)

    def test_is_verified_defaults_false(self):
        user = CustomUser.objects.create_user(
            email="unverified@example.com",
            username="unverified",
            password="strongpass123",
        )
        self.assertFalse(user.is_verified)

    def test_email_must_be_unique(self):
        CustomUser.objects.create_user(
            email="dup@example.com", username="u1", password="strongpass123"
        )
        with self.assertRaises(IntegrityError):
            CustomUser.objects.create_user(
                email="dup@example.com", username="u2", password="strongpass123"
            )

    def test_str_returns_email(self):
        user = CustomUser.objects.create_user(
            email="str@example.com", username="struser", password="strongpass123"
        )
        self.assertEqual(str(user), "str@example.com")


class AccountDeactivationTests(StoreTestCase):
    """The profile danger-zone: deactivation is a soft-disable gated by a
    typed-email confirmation, never a hard delete (orders must stay on file)."""

    def setUp(self):
        self.user = make_user("deact")
        self.client.force_login(self.user)

    def test_wrong_confirmation_keeps_account_active(self):
        response = self.client.post(
            reverse("deactivate_account"), {"confirm": "someoneelse@example.com"}
        )
        self.assertRedirects(response, reverse("profile_view"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_typed_email_deactivates_and_logs_out(self):
        response = self.client.post(
            reverse("deactivate_account"), {"confirm": "deact@example.com"}
        )
        self.assertRedirects(response, reverse("home"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        # Session cleared: a protected page now bounces to login.
        self.assertEqual(self.client.get(reverse("profile_view")).status_code, 302)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("deactivate_account")).status_code, 405)
