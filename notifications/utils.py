# notifications/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

def send_automated_notification(subject, template_name, context, recipient_list, fail_silently=True):
    if not recipient_list:
        return
    try:
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@allthings.com')
        send_mail(
            subject, plain_message, from_email, recipient_list,
            html_message=html_message, fail_silently=fail_silently, 
        )
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {e}")