from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from marketplace.models import ProviderInquiry
from orders.models import ServiceOrder, ServiceQuote, OrderItem
from .models import Notification
from .tasks import send_notification_email_task


# --- 1. PRE-BOOKING INQUIRIES ---
@receiver(post_save, sender=ProviderInquiry)
def create_inquiry_notification(sender, instance, created, **kwargs):
    if created and instance.provider and instance.provider.user:
        Notification.objects.create(
            recipient=instance.provider.user,
            notification_type='INQUIRY',
            title='New Pre-Booking Inquiry',
            message=f"{instance.sender.username} asked: {instance.message[:50]}...",
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.id
        )


# --- 2. SERVICE ORDER CREATION & STATUS TRANSITIONS (Provider Portal Actions) ---
@receiver(pre_save, sender=ServiceOrder)
def capture_previous_service_status(sender, instance, **kwargs):
    if instance.pk:
        old = ServiceOrder.objects.filter(pk=instance.pk).values('status').first()
        instance._old_status = old['status'] if old else None
    else:
        instance._old_status = None

@receiver(post_save, sender=ServiceOrder)
def create_order_notification(sender, instance, created, **kwargs):
    ct = ContentType.objects.get_for_model(instance)
    service_name = instance.service.name if instance.service else instance.reference_code

    if created:
        if instance.provider and instance.provider.user:
            Notification.objects.create(
                recipient=instance.provider.user,
                notification_type='ORDER',
                title=f"New Service Booking ({instance.reference_code})",
                message=f"You have a new booking request for '{service_name}' from {instance.customer.username}.",
                content_type=ct,
                object_id=instance.id
            )
        return

    # Status changed by Provider in the Provider Dashboard
    old_status = getattr(instance, '_old_status', None)
    if old_status and old_status != instance.status:
        if instance.status == 'ACCEPTED':
            Notification.objects.create(
                recipient=instance.customer,
                notification_type='ORDER',
                title=f"Booking Accepted ({instance.reference_code})",
                message=f"{instance.provider.business_name} accepted your request for '{service_name}'. Please complete payment to lock in your schedule.",
                content_type=ct,
                object_id=instance.id
            )
        elif instance.status == 'IN_PROGRESS':
            Notification.objects.create(
                recipient=instance.customer,
                notification_type='ORDER',
                title=f"Service In Progress ({instance.reference_code})",
                message=f"Work has officially started on '{service_name}'.",
                content_type=ct,
                object_id=instance.id
            )
        elif instance.status == 'COMPLETED':
            Notification.objects.create(
                recipient=instance.customer,
                notification_type='ORDER',
                title=f"Job Marked Completed ({instance.reference_code})",
                message=f"{instance.provider.business_name} marked '{service_name}' as completed. Please confirm satisfaction within 72 hours or report an issue.",
                content_type=ct,
                object_id=instance.id
            )
        elif instance.status == 'DECLINED':
            Notification.objects.create(
                recipient=instance.customer,
                notification_type='ORDER',
                title=f"Booking Declined ({instance.reference_code})",
                message=f"Unfortunately, the provider is unavailable for '{service_name}' on your requested date.",
                content_type=ct,
                object_id=instance.id
            )


# --- 3. CUSTOM SERVICE QUOTES SENT BY PROVIDER ---
@receiver(post_save, sender=ServiceQuote)
def notify_customer_on_quote(sender, instance, created, **kwargs):
    if created and instance.order:
        s_order = instance.order
        service_name = s_order.service.name if s_order.service else s_order.reference_code
        Notification.objects.create(
            recipient=s_order.customer,
            notification_type='ORDER',
            title=f"New Custom Quote: NGN {instance.total_amount:,.2f}",
            message=f"{s_order.provider.business_name} sent a custom quote for '{service_name}'. Review and accept to proceed.",
            content_type=ContentType.objects.get_for_model(s_order),
            object_id=s_order.id
        )


# --- 4. PHYSICAL PRODUCT LOGISTICS UPDATES (Vendor Accepts / Rider Picks Up / Delivered) ---
@receiver(pre_save, sender=OrderItem)
def capture_previous_item_status(sender, instance, **kwargs):
    if instance.pk:
        old = OrderItem.objects.filter(pk=instance.pk).values('status').first()
        instance._old_status = old['status'] if old else None
    else:
        instance._old_status = None

@receiver(post_save, sender=OrderItem)
def notify_customer_on_item_logistics(sender, instance, created, **kwargs):
    if created:
        return
    old_status = getattr(instance, '_old_status', None)
    if not old_status or old_status == instance.status:
        return

    product_name = instance.product.name if instance.product else "your item"
    order_ct = ContentType.objects.get_for_model(instance.order)

    if instance.status == 'ACCEPTED':
        Notification.objects.create(
            recipient=instance.order.customer,
            notification_type='ORDER',
            title=f"Vendor Processing: {product_name}",
            message=f"The vendor is preparing '{product_name}' ({instance.order.reference}) for dispatch.",
            content_type=order_ct,
            object_id=instance.order.id
        )
    elif instance.status == 'PICKED_UP':
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
            message=f"'{product_name}' has been marked delivered. Please confirm receipt or report any issue within 72 hours.",
            content_type=order_ct,
            object_id=instance.order.id
        )


# --- 5. MASTER EMAIL DISPATCHER (Fires on EVERY Notification created) ---
@receiver(post_save, sender=Notification)
def trigger_email_alert(sender, instance, created, **kwargs):
    if created and instance.recipient and instance.recipient.email:
        display_name = instance.recipient.first_name or instance.recipient.username
        send_notification_email_task.delay(
            user_email=instance.recipient.email,
            user_first_name=display_name,
            title=instance.title,
            message=instance.message,
            action_path=instance.link
        )