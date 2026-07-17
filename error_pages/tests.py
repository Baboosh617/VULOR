from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from error_pages import views
from vulor.testing import StoreTestCase


class ErrorPagesTests(StoreTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, path):
        # AuthenticationMiddleware normally attaches request.user; the base
        # template and context processors read it, so set it explicitly on the
        # bare RequestFactory request the error handlers receive here.
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return request

    def test_custom_404(self):
        response = views.custom_404(self._request("/missing/"), Exception("not found"))
        self.assertEqual(response.status_code, 404)

    def test_custom_403(self):
        response = views.custom_403(self._request("/forbidden/"), Exception("forbidden"))
        self.assertEqual(response.status_code, 403)

    def test_custom_400(self):
        response = views.custom_400(self._request("/bad/"), Exception("bad request"))
        self.assertEqual(response.status_code, 400)

    def test_custom_500(self):
        response = views.custom_500(self._request("/error/"))
        self.assertEqual(response.status_code, 500)
