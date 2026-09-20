from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from orders.models import OrderItem, ServiceOrder

class Feedback(models.Model):
    class TransactionType(models.TextChoices):
        PRODUCT = 'PRODUCT', 'Product Purchase'
        SERVICE = 'SERVICE', 'Service Booking'

    class ModerationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Moderation'
        APPROVED = 'APPROVED', 'Published'
        REJECTED = 'REJECTED', 'Removed'

    # Core Relationships
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='given_feedback'
    )
    target_provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='received_feedback', 
        help_text="The vendor or service provider being reviewed."
    )
    
    # Transaction Links (Verified Purchase Integrity)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    order_item = models.OneToOneField(
        OrderItem, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='feedback'
    )
    
    # --- UPDATED: Now links directly to the new ServiceOrder engine ---
    service_order = models.OneToOneField(
        ServiceOrder, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='feedback'
    )

    # Denormalized links for fast querying
    product = models.ForeignKey(
        'marketplace.Product', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='reviews'
    )
    service = models.ForeignKey(
        'marketplace.Service', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='reviews'
    )

    # Review Content
    overall_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    public_review = models.TextField(blank=True, null=True, help_text="Visible to other customers.")
    private_feedback = models.TextField(blank=True, null=True, help_text="Only visible to All Things support and admins.")
    
    # System Flags
    is_verified = models.BooleanField(default=False, help_text="True if generated directly from a completed transaction.")
    helpful_votes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=ModerationStatus.choices, default=ModerationStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.overall_rating} Stars by {self.customer.username}"

class FeedbackAttribute(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='attributes')
    attribute_name = models.CharField(max_length=50)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    def __str__(self):
        return f"{self.attribute_name}: {self.rating}"

class FeedbackPhoto(models.Model):
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='feedback_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)