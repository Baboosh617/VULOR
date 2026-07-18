from django.contrib.auth.signals import user_logged_in, user_login_failed, user_logged_out

import logging

logger = logging.getLogger('django.security.login')


def get_client_ip(request):
    if request is None:
        return 'unknown'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def login_success(sender, request, user, **kwargs):
    logger.info(f"Login SUCCESS for {user.email} from IP {get_client_ip(request)}")


def login_failed(sender, credentials, request, **kwargs):
    logger.warning(f"Login FAILED for {credentials.get('email')} from IP {get_client_ip(request)}")


def logout_success(sender, request, user, **kwargs):
    # user is None when an anonymous session hits the logout view
    email = getattr(user, 'email', 'anonymous')
    logger.info(f"Logout SUCCESS for {email} from IP {get_client_ip(request)}")


user_logged_in.connect(login_success)
user_login_failed.connect(login_failed)
user_logged_out.connect(logout_success)
