from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

@shared_task
def send_notification_email_task(user_email, user_first_name, title, message, action_path='/notifications/'):
    subject = f"AllThings: {title}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@allthings.com')
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    
    html_content = render_to_string('emails/notification_alert.html', {
        'first_name': user_first_name,
        'title': title,
        'message': message,
        'action_url': f"{site_url}{action_path}"
    })
    
    msg = EmailMultiAlternatives(subject, message, from_email, [user_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    return f"Email alert '{title}' sent to {user_email}"