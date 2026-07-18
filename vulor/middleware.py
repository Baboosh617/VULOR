from django.http import HttpResponse

# Mirrors nginx's client_max_body_size 6M (nginx.conf) so the Docker and
# Render paths enforce the same cap. Render has no nginx in front — without
# this, Django's 5 MB receipt check only runs after gunicorn has already
# read an arbitrarily large body to a temp file, an easy bandwidth/disk
# drain. 6 MB = the largest allowed upload (5 MB) plus multipart overhead;
# no legitimate request body in this app comes near it.
MAX_BODY_BYTES = 6 * 1024 * 1024


class BodySizeLimitMiddleware:
    """Reject oversized request bodies from Content-Length, before any of
    the body is read."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            content_length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > MAX_BODY_BYTES:
            return HttpResponse(
                'Request body too large.', status=413, content_type='text/plain'
            )
        return self.get_response(request)
