import logging

from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)


class ResilientAccountAdapter(DefaultAccountAdapter):
    """Every allauth email (verification, password reset) passes through
    send_mail. The default adapter sends synchronously inside the request with
    no error handling, so an unreachable SMTP server turns signup into a 500
    after the user row is already committed. Catch and log instead: the flow
    completes, and allauth re-sends the verification email on the next login
    attempt while the address is unverified, so a transient outage self-heals
    — EXCEPT within the confirm_email cooldown window (default 180s per
    address, ACCOUNT_RATE_LIMITS['confirm_email']): allauth's own
    should_send_confirmation_mail() silently skips the send before send_mail
    is ever called, which looks identical to a successful send from the
    outside (still 302s to confirm-email) unless logged explicitly here.
    """

    def should_send_confirmation_mail(self, request, email_address, signup):
        will_send = super().should_send_confirmation_mail(request, email_address, signup)
        if will_send:
            msg = f"[email-workflow] will send confirmation mail to {email_address.email} (signup={signup})"
        else:
            msg = (
                f"[email-workflow] SKIPPED confirmation mail to {email_address.email} "
                f"(signup={signup}) — allauth's confirm_email cooldown rate-limit "
                f"blocked it (default: 1 per 180s per address); send_mail will NOT "
                f"be called for this request"
            )
        print(msg)
        logger.info(msg)
        return will_send

    def send_mail(self, template_prefix, email, context):
        print(f"[email-workflow] sending '{template_prefix}' to {email}...")
        logger.info(f"[email-workflow] sending '{template_prefix}' to {email}")
        try:
            super().send_mail(template_prefix, email, context)
        except Exception:
            print(f"[email-workflow] FAILED '{template_prefix}' to {email} — see traceback below")
            logger.error(
                f"[email-workflow] Failed to send allauth email '{template_prefix}' to {email}",
                exc_info=True,
            )
        else:
            print(f"[email-workflow] SENT '{template_prefix}' to {email}")
            logger.info(f"[email-workflow] Sent allauth email '{template_prefix}' to {email}")
