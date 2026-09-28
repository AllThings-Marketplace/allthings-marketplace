from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from marketplace.models import ProviderInquiry
from orders.models import ServiceOrder
from .models import Notification

# 1. Listen for new Pre-Booking Inquiries
@receiver(post_save, sender=ProviderInquiry)
def create_inquiry_notification(sender, instance, created, **kwargs):
    if created:  # Only trigger when it's first created, not if it's just being edited
        Notification.objects.create(
            recipient=instance.provider.user,
            notification_type='INQUIRY',
            title='New Pre-Booking Inquiry',
            message=f"{instance.sender.username} asked: {instance.message[:50]}...",
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.id
        )

# 2. Example: Listen for Order Status Changes
@receiver(post_save, sender=ServiceOrder)
def create_order_notification(sender, instance, created, **kwargs):
    # If a customer just placed a new order
    if created:
        Notification.objects.create(
            recipient=instance.provider.user,
            notification_type='ORDER',
            title='New Service Order!',
            message=f"You have a new booking request from {instance.customer.username}.",
            content_type=ContentType.objects.get_for_model(instance),
            object_id=instance.id
        )