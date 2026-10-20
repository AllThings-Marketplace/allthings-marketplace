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

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    
    # What the notification actually says
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- THE MAGIC: Generic Foreign Key ---
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
        if self.content_type and self.object_id:
            model_name = self.content_type.model
            if model_name == 'supportticket' and self.content_object:
                return reverse('orders:ticket_detail', args=[self.content_object.ticket_reference])
            elif model_name == 'serviceorder':
                return reverse('orders:order_history')
            elif model_name == 'order':
                return reverse('orders:order_details', args=[self.object_id])
            elif model_name == 'providerinquiry':
                return reverse('marketplace:inbox')
        if self.notification_type == 'INQUIRY':
            return reverse('marketplace:inbox')
        if self.notification_type == 'ORDER':
            return reverse('orders:order_history')
        return reverse('notifications:history')

    def __str__(self):
        return f"{self.notification_type} for {self.recipient.username} - {self.title}"