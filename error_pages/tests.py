from django.test import TestCase, RequestFactory
from error_pages import views


class ErrorPagesTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_custom_404(self):
        request = self.factory.get("/missing/")
        response = views.custom_404(request, Exception("not found"))
        self.assertEqual(response.status_code, 404)

    def test_custom_403(self):
        request = self.factory.get("/forbidden/")
        response = views.custom_403(request, Exception("forbidden"))
        self.assertEqual(response.status_code, 403)

    def test_custom_400(self):
        request = self.factory.get("/bad/")
        response = views.custom_400(request, Exception("bad request"))
        self.assertEqual(response.status_code, 400)

    def test_custom_500(self):
        request = self.factory.get("/error/")
        response = views.custom_500(request)
        self.assertEqual(response.status_code, 500)
