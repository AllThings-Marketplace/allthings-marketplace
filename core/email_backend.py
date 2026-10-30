import base64
import logging
import re
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

logger = logging.getLogger(__name__)

EMAIL_PARSE_REGEX = re.compile(r'^(.*?)\s*<([^>]+)>$')


def parse_address(raw_address, fallback_name="AllThings Marketplace"):
    """
    Splits 'AllThings Marketplace <noreply@allthings.com>' or 'user@example.com'
    into {'name': '...', 'email': '...'}.
    """
    raw = str(raw_address or '').strip()
    match = EMAIL_PARSE_REGEX.match(raw)
    if match:
        name = match.group(1).strip().strip('"').strip("'") or fallback_name
        email = match.group(2).strip()
        return {"name": name, "email": email}
    return {"name": fallback_name, "email": raw}


class BrevoAPIEmailBackend(BaseEmailBackend):
    """
    Production-grade Django EmailBackend that sends all emails over HTTPS (Port 443)
    via Brevo's v3 Transactional REST API (https://api.brevo.com/v3/smtp/email).

    Fallback chain:
    1. Brevo HTTPS API (Port 443) when BREVO_API_KEY (or an 'xkeysib-' key) is present.
    2. Standard Django SMTP with a strict timeout if only SMTP credentials are set.
    3. Django Console backend in local development when no credentials are set.
    """
    api_url = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.timeout = getattr(settings, "EMAIL_TIMEOUT", 8)

        brevo_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not brevo_key:
            smtp_pass = getattr(settings, "EMAIL_HOST_PASSWORD", "").strip()
            if smtp_pass.startswith("xkeysib-"):
                brevo_key = smtp_pass
        self.api_key = brevo_key

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        # If no Brevo API key is configured, fall back to SMTP (with timeout) or Console
        if not self.api_key:
            if getattr(settings, "EMAIL_HOST_USER", "") and getattr(settings, "EMAIL_HOST_PASSWORD", ""):
                try:
                    smtp_backend = SMTPEmailBackend(
                        fail_silently=self.fail_silently,
                        timeout=self.timeout,
                    )
                    return smtp_backend.send_messages(email_messages)
                except Exception as exc:
                    logger.error("Fallback SMTP backend failed: %s", exc)
                    if not self.fail_silently:
                        raise
                    return 0

            console_backend = ConsoleEmailBackend(fail_silently=self.fail_silently)
            return console_backend.send_messages(email_messages)

        sent_count = 0
        for message in email_messages:
            if self._send_via_brevo_https(message):
                sent_count += 1
        return sent_count

    def _send_via_brevo_https(self, message):
        if not message.to:
            return False

        default_from = getattr(
            settings,
            "DEFAULT_FROM_EMAIL",
            "AllThings Marketplace <noreply@allthings.com>",
        )
        sender_info = parse_address(message.from_email or default_from)
        # If message.from_email had no display name, keep the brand name
        if sender_info["name"] == sender_info["email"]:
            sender_info["name"] = "AllThings Marketplace"

        to_list = [parse_address(addr, fallback_name=addr.split("@")[0]) for addr in message.to if addr]
        cc_list = [parse_address(addr, fallback_name=addr.split("@")[0]) for addr in (message.cc or []) if addr]
        bcc_list = [parse_address(addr, fallback_name=addr.split("@")[0]) for addr in (message.bcc or []) if addr]

        text_body = ""
        html_body = ""

        if getattr(message, "content_subtype", "plain") == "html":
            html_body = message.body or ""
        else:
            text_body = message.body or ""

        # Extract HTML body from EmailMultiAlternatives if attached
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_body = content
                break

        # Brevo requires at least htmlContent or textContent
        if not html_body and text_body:
            escaped_text = (
                text_body.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            html_body = (
                f"<div style='font-family:sans-serif;font-size:15px;color:#1e293b;"
                f"line-height:1.6;max-width:560px;margin:0 auto;'>{escaped_text}</div>"
            )

        payload = {
            "sender": sender_info,
            "to": to_list,
            "subject": str(message.subject or ""),
        }
        if text_body:
            payload["textContent"] = str(text_body)
        if html_body:
            payload["htmlContent"] = str(html_body)
        if cc_list:
            payload["cc"] = cc_list
        if bcc_list:
            payload["bcc"] = bcc_list
        if getattr(message, "reply_to", None):
            first_reply = message.reply_to[0]
            if first_reply:
                payload["replyTo"] = parse_address(first_reply)

        # Support file attachments if present on the EmailMessage
        attachments = []
        for attachment in getattr(message, "attachments", []):
            if isinstance(attachment, tuple) and len(attachment) >= 2:
                filename, content = attachment[0], attachment[1]
                if isinstance(content, str):
                    content = content.encode("utf-8")
                if isinstance(content, bytes):
                    attachments.append({
                        "name": filename,
                        "content": base64.b64encode(content).decode("ascii"),
                    })
        if attachments:
            payload["attachment"] = attachments

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "accept": "application/json",
                    "api-key": self.api_key,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code in (200, 201, 202):
                logger.info(
                    "Brevo HTTPS API delivered email '%s' to %s",
                    message.subject,
                    ", ".join(message.to),
                )
                return True

            logger.error(
                "Brevo HTTPS API rejected email '%s' (HTTP %s): %s",
                message.subject,
                response.status_code,
                response.text,
            )
            if not self.fail_silently:
                raise RuntimeError(f"Brevo API HTTP {response.status_code}: {response.text}")
            return False

        except Exception as exc:
            logger.error("Brevo HTTPS API error sending '%s': %s", message.subject, exc)
            if not self.fail_silently:
                raise
            return False