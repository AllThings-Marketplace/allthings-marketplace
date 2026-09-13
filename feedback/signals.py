# feedback/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from orders.models import OrderItem, JobBooking
from notifications.utils import send_automated_notification

@receiver(post_save, sender=OrderItem)
def trigger_product_feedback_invite(sender, instance, created, **kwargs):
    # Triggers only when status is DELIVERED and no feedback record is linked yet
    if instance.status == 'DELIVERED' and not hasattr(instance, 'feedback'):
        recipient = instance.order.customer
        
        # We will build the route for this in Phase 3
        feedback_url = f"{settings.SITE_URL}/feedback/product/{instance.id}/"
        
        send_automated_notification(
            subject=f"How was your {instance.product.name}?",
            template_name='emails/feedback_invite.html',
            context={
                'first_name': instance.order.first_name or recipient.username,
                'item_name': instance.product.name,
                'feedback_url': feedback_url,
                'type': 'product'
            },
            recipient_list=[recipient.email]
        )

@receiver(post_save, sender=JobBooking)
def trigger_service_feedback_invite(sender, instance, created, **kwargs):
    # Triggers only when status is COMPLETED and no feedback record is linked yet
    if instance.status == 'COMPLETED' and not hasattr(instance, 'feedback'):
        recipient = instance.order.customer
        provider_name = instance.provider.provider_profile.business_name if hasattr(instance.provider, 'provider_profile') else instance.provider.username
        
        feedback_url = f"{settings.SITE_URL}/feedback/service/{instance.id}/"
        
        send_automated_notification(
            subject=f"How was your service with {provider_name}?",
            template_name='emails/feedback_invite.html',
            context={
                'first_name': instance.order.first_name or recipient.username,
                'item_name': instance.service.name,
                'provider_name': provider_name,
                'feedback_url': feedback_url,
                'type': 'service'
            },
            recipient_list=[recipient.email]
        )