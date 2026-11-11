import threading
from datetime import timedelta
from django.db import transaction, close_old_connections
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from orders.models import OrderItem
from .models import Notification
from .tasks import send_notification_email_task


def _dispatch_email_in_background(**kwargs):
    """
    Sends the transactional HTML email via Brevo HTTPS API in a non-blocking
    daemon thread so HTTP requests return immediately even without a Celery worker.
    """
    def _runner():
        close_old_connections()
        try:
            send_notification_email_task(**kwargs)
        except Exception:
            pass
        finally:
            close_old_connections()

    threading.Thread(target=_runner, daemon=True).start()


# --- 1. PHYSICAL PRODUCT LOGISTICS UPDATES (Rider Picked Up / Delivered) ---
@receiver(pre_save, sender=OrderItem)
def capture_previous_item_status(sender, instance, **kwargs):
    if instance.pk:
        old = OrderItem.objects.filter(pk=instance.pk).values('status').first()
        instance._old_status = old['status'] if old else None
    else:
        instance._old_status = None


@receiver(post_save, sender=OrderItem)
def notify_customer_on_item_logistics(sender, instance, created, **kwargs):
    """
    Fires when an OrderItem transitions to PICKED_UP or DELIVERED
    (e.g., via courier webhook or admin logistics update).
    Note: ACCEPTED, READY_FOR_PICKUP, and CANCELLED are handled directly in dashboard/views.py.
    """
    if created:
        return
    old_status = getattr(instance, '_old_status', None)
    if not old_status or old_status == instance.status:
        return

    product_name = instance.product.name if instance.product else "your item"
    order_ct = ContentType.objects.get_for_model(instance.order)

    if instance.status == 'PICKED_UP':
        Notification.objects.create(
            recipient=instance.order.customer,
            notification_type='ORDER',
            title=f"Item In Transit: {product_name}",
            message=f"Your item '{product_name}' has been picked up by the rider! Have your 6-digit delivery PIN ({instance.delivery_code}) ready.",
            content_type=order_ct,
            object_id=instance.order.id
        )
    elif instance.status == 'DELIVERED':
        Notification.objects.create(
            recipient=instance.order.customer,
            notification_type='ORDER',
            title=f"Item Delivered: {product_name}",
            message=f"'{product_name}' has been marked delivered. Please confirm receipt with your 6-digit PIN or report any issue within 72 hours.",
            content_type=order_ct,
            object_id=instance.order.id
        )


# --- 2. MASTER EMAIL DISPATCHER (With 15-Minute Cooldown on Live Order Chat) ---
@receiver(post_save, sender=Notification)
def trigger_email_alert(sender, instance, created, **kwargs):
    if not (created and instance.recipient and instance.recipient.email):
        return

    # Throttle rapid-fire live Order Chat emails:
    # If the user already has an unread MESSAGE alert for the same booking within the last 15 minutes,
    # keep the in-app Bell alert but skip sending another email.
    if instance.notification_type == 'MESSAGE' and instance.content_type_id and instance.object_id:
        cooldown_cutoff = timezone.now() - timedelta(minutes=15)
        recent_unread_chat_exists = Notification.objects.filter(
            recipient=instance.recipient,
            notification_type='MESSAGE',
            content_type_id=instance.content_type_id,
            object_id=instance.object_id,
            is_read=False,
            created_at__gte=cooldown_cutoff,
        ).exclude(pk=instance.pk).exists()

        if recent_unread_chat_exists:
            return

    display_name = instance.recipient.first_name or instance.recipient.username
    email_kwargs = {
        'user_email': instance.recipient.email,
        'user_first_name': display_name,
        'title': instance.title,
        'message': instance.message,
        'action_path': instance.link,
    }

    transaction.on_commit(lambda: _dispatch_email_in_background(**email_kwargs))