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
