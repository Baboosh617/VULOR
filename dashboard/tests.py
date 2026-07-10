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
