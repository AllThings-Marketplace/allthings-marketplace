from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from accounts.models import ProviderProfile
from notifications.models import Notification
from orders.models import OrderItem, ServiceOrder
from .models import Feedback


@receiver(pre_save, sender=OrderItem)
def _capture_order_item_old_status(sender, instance, **kwargs):
    if instance.pk:
        old = OrderItem.objects.filter(pk=instance.pk).values('status').first()
        instance._old_feedback_status = old['status'] if old else None
    else:
        instance._old_feedback_status = None


@receiver(post_save, sender=OrderItem)
def trigger_product_feedback_invite(sender, instance, created, **kwargs):
    """
    Sends an in-app Bell & Brevo Email review invitation once an OrderItem
    reaches COMPLETED (6-digit PIN verified) and has not been reviewed yet.
    """
    if created:
        return
    old_status = getattr(instance, '_old_feedback_status', None)
    if old_status == instance.status:
        return

    if instance.status == 'COMPLETED' and not hasattr(instance, 'feedback') and instance.product:
        Notification.objects.create(
            recipient=instance.order.customer,
            notification_type='REVIEW',
            title=f"Rate Your Purchase: {instance.product.name[:40]}",
            message=f"How was '{instance.product.name}'? Share your verified review to help other shoppers on AllThings.",
            content_type=ContentType.objects.get_for_model(instance.product),
            object_id=instance.product.id,
        )


@receiver(pre_save, sender=ServiceOrder)
def _capture_service_order_old_status(sender, instance, **kwargs):
    if instance.pk:
        old = ServiceOrder.objects.filter(pk=instance.pk).values('status').first()
        instance._old_feedback_status = old['status'] if old else None
    else:
        instance._old_feedback_status = None


@receiver(post_save, sender=ServiceOrder)
def trigger_service_feedback_invite(sender, instance, created, **kwargs):
    """
    Sends an in-app Bell & Brevo Email review invitation when a ServiceOrder
    is marked CONFIRMED and escrow is released.
    """
    if created:
        return
    old_status = getattr(instance, '_old_feedback_status', None)
    if old_status == instance.status:
        return

    if instance.status == 'CONFIRMED' and not hasattr(instance, 'feedback') and instance.service:
        provider_name = instance.provider.business_name if instance.provider else "your provider"
        Notification.objects.create(
            recipient=instance.customer,
            notification_type='REVIEW',
            title=f"Rate Your Service with {provider_name[:35]}",
            message=f"Your booking for '{instance.service.name}' is complete! Leave a verified review for {provider_name}.",
            content_type=ContentType.objects.get_for_model(instance.service),
            object_id=instance.service.id,
        )


@receiver(post_save, sender=Feedback)
def handle_new_feedback_published(sender, instance, created, **kwargs):
    """
    1. Recalculates the provider's dynamic trust_score (scale 0-100) from all APPROVED reviews.
    2. Sends a Bell + Email alert to the provider when a new review is submitted.
    """
    provider_user = instance.target_provider
    if not provider_user:
        return

    profile = ProviderProfile.objects.filter(user=provider_user).first()
    if profile:
        avg_stars = Feedback.objects.filter(
            target_provider=provider_user,
            status=Feedback.ModerationStatus.APPROVED
        ).aggregate(avg=Avg('overall_rating'))['avg']

        if avg_stars is not None:
            # Map 1.0 - 5.0 star average to a 20 - 100 trust score
            new_trust_score = max(20, min(100, int(round(float(avg_stars) * 20))))
            if profile.trust_score != new_trust_score:
                profile.trust_score = new_trust_score
                profile.save(update_fields=['trust_score'])

    if created and instance.status == Feedback.ModerationStatus.APPROVED:
        item_label = (
            instance.product.name if instance.product
            else (instance.service.name if instance.service else "your store")
        )
        target_obj = instance.product or instance.service or profile
        ct = ContentType.objects.get_for_model(target_obj) if target_obj else None
        obj_id = target_obj.id if target_obj else None

        Notification.objects.create(
            recipient=provider_user,
            notification_type='REVIEW',
            title=f"New {instance.overall_rating}-Star Verified Review!",
            message=f"{instance.customer.username} left a {instance.overall_rating}-star review on '{item_label}'.",
            content_type=ct,
            object_id=obj_id,
        )