import logging

from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)


class ResilientAccountAdapter(DefaultAccountAdapter):
    """Every allauth email (verification, password reset) passes through
    send_mail. The default adapter sends synchronously inside the request with
    no error handling, so an unreachable SMTP server turns signup into a 500
    after the user row is already committed. Catch and log instead: the flow
    completes, and allauth re-sends the verification email on the next login
    attempt while the address is unverified, so a transient outage self-heals.
    """

    def send_mail(self, template_prefix, email, context):
        try:
            super().send_mail(template_prefix, email, context)
        except Exception:
            logger.error(
                f"Failed to send allauth email '{template_prefix}' to {email}",
                exc_info=True,
            )
