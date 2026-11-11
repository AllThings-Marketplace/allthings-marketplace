import logging
import os
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def _resolve_site_url():
    """
    Resolves the public production base URL for email CTA buttons.
    Priority: settings.SITE_URL -> RAILWAY_PUBLIC_DOMAIN -> ALLOWED_HOSTS -> localhost fallback.
    """
    configured = getattr(settings, 'SITE_URL', '').strip().rstrip('/')
    if configured and '127.0.0.1' not in configured and 'localhost' not in configured:
        return configured

    railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip().rstrip('/')
    if railway_domain:
        if not railway_domain.startswith('http'):
            return f"https://{railway_domain}"
        return railway_domain

    allowed = getattr(settings, 'ALLOWED_HOSTS', [])
    for host in allowed:
        if host and host not in ('*', 'localhost', '127.0.0.1', '[::1]') and not host.startswith('.'):
            return f"https://{host}"

    return configured or 'http://127.0.0.1:8000'


@shared_task
def send_notification_email_task(user_email, user_first_name, title, message, action_path='/notifications/'):
    if not user_email:
        return "Skipped: No recipient email"

    try:
        subject = f"AllThings: {title}"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'AllThings Marketplace <noreply@allthings.com>')
        site_url = _resolve_site_url()
        safe_path = action_path if str(action_path).startswith('/') else f"/{action_path}"

        html_content = render_to_string('emails/notification_alert.html', {
            'first_name': user_first_name,
            'title': title,
            'message': message,
            'action_url': f"{site_url}{safe_path}",
        })

        msg = EmailMultiAlternatives(subject, message, from_email, [user_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return f"Email alert '{title}' sent to {user_email}"
    except Exception as exc:
        logger.error("Failed to send notification email '%s' to %s: %s", title, user_email, exc)
        return f"Failed: {exc}"