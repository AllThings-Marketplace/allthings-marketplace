from django.db import models
from django.conf import settings
from django.urls import reverse
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('ORDER', 'Order Update'),
        ('INQUIRY', 'New Pre-Booking Inquiry'),
        ('MESSAGE', 'Active Order Message'),
        ('REVIEW', 'New Review'),
        ('SYSTEM', 'System Alert'),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)

    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Generic Foreign Key to target object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    @property
    def link(self):
        """Dynamically resolves the destination URL for the navbar bell & email button."""
        try:
            if self.content_type and self.object_id:
                model_name = self.content_type.model

                if model_name == 'customerrequest':
                    return reverse('marketplace:request_detail', args=[self.object_id])

                elif model_name == 'requestmatch' and self.content_object:
                    return reverse('marketplace:request_detail', args=[self.content_object.customer_request_id])

                elif model_name == 'supportticket' and self.content_object:
                    return reverse('orders:ticket_detail', args=[self.content_object.ticket_reference])

                elif model_name == 'serviceorder':
                    if self.notification_type == 'MESSAGE':
                        return reverse('orders:order_chat', args=[self.object_id])
                    if hasattr(self.recipient, 'provider_profile') and self.content_object and self.content_object.provider_id == self.recipient.provider_profile.id:
                        return reverse('dashboard:provider_dashboard')
                    return reverse('orders:order_history')

                elif model_name == 'order':
                    if self.content_object and self.content_object.customer_id == self.recipient_id:
                        return reverse('orders:order_details', args=[self.object_id])
                    return reverse('dashboard:vendor_orders')

                elif model_name == 'providerinquiry':
                    return reverse('marketplace:inbox')

                elif model_name == 'providerprofile':
                    if self.content_object and self.content_object.verification_status == 'ACTIVE':
                        return reverse('dashboard:provider_dashboard')
                    return reverse('accounts:provider_status')

                elif model_name == 'product':
                    if self.content_object and self.content_object.status == 'APPROVED' and self.content_object.slug:
                        return reverse('marketplace:product_detail', args=[self.content_object.slug])
                    return reverse('dashboard:provider_dashboard')

                elif model_name == 'service':
                    if self.content_object and self.content_object.status == 'APPROVED' and self.content_object.slug:
                        return reverse('marketplace:service_detail', args=[self.content_object.slug])
                    return reverse('dashboard:provider_dashboard')

            if self.notification_type == 'INQUIRY':
                return reverse('marketplace:inbox')
            if self.notification_type == 'ORDER':
                return reverse('orders:order_history')
        except Exception:
            pass

        return reverse('notifications:history')

    def __str__(self):
        return f"{self.notification_type} for {self.recipient.username} - {self.title}"