from django.urls import reverse
from vulor.testing import StoreTestCase, make_user
from django.test import TestCase, override_settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail.backends.base import BaseEmailBackend
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


class BrokenEmailBackend(BaseEmailBackend):
    """Simulates an unreachable SMTP server (connection timeout)."""

    def send_messages(self, email_messages):
        raise TimeoutError(110, "Connection timed out")


# Allauth's confirm_email cooldown lives in the default cache; the dev cache
# is file-based and outlives both test isolation and whole test runs, so it
# would silently skip the verification send on reruns. LocMemCache is fresh
# per process; distinct emails per test keep the cooldown from crossing tests.
@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class RegistrationEmailTests(StoreTestCase):
    @staticmethod
    def signup_data(username):
        return {
            "username": username,
            "email": f"{username}@example.com",
            "password1": "strongpass123!",
            "password2": "strongpass123!",
        }

    def test_register_sends_verification_email(self):
        response = self.client.post(reverse("register"), self.signup_data("newbuyer"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email="newbuyer@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newbuyer@example.com", mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND="accounts.tests.BrokenEmailBackend")
    def test_register_survives_smtp_outage(self):
        """An unreachable SMTP server must not 500 the signup after the user
        row is committed — the resilient adapter logs and lets the flow finish;
        allauth re-sends verification on the next login attempt."""
        with self.assertLogs("accounts.adapter", level="ERROR"):
            response = self.client.post(reverse("register"), self.signup_data("outagebuyer"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email="outagebuyer@example.com").exists())
