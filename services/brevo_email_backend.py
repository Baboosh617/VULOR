import base64
import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoAPIEmailBackend(BaseEmailBackend):
    """Sends mail via Brevo's HTTPS API instead of SMTP.

    Render's free tier blocks outbound SMTP ports (25/465/587); HTTPS on
    443 is not blocked, so this keeps transactional email working there.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.error("Brevo API send failed for %s", message.to, exc_info=True)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        name, email = parseaddr(message.from_email)
        payload = {
            "sender": {"email": email, "name": name} if name else {"email": email},
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }
        html = next(
            (content for content, mimetype in getattr(message, "alternatives", [])
             if mimetype == "text/html"),
            None,
        )
        if html:
            payload["htmlContent"] = html
        if message.cc:
            payload["cc"] = [{"email": addr} for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": addr} for addr in message.bcc]
        if message.reply_to:
            r_name, r_email = parseaddr(message.reply_to[0])
            payload["replyTo"] = {"email": r_email, "name": r_name} if r_name else {"email": r_email}
        if message.attachments:
            payload["attachment"] = [self._encode_attachment(a) for a in message.attachments]

        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json"},
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Brevo API error {response.status_code}: {response.text}")

    @staticmethod
    def _encode_attachment(attachment):
        filename, content, mimetype = attachment
        if isinstance(content, str):
            content = content.encode()
        return {"name": filename, "content": base64.b64encode(content).decode()}
