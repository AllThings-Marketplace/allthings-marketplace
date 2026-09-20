import uuid
import random
from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.conf import settings
from accounts.models import ProviderProfile
from marketplace.models import Product, Service, ProductVariant, ServicePackage

# --- 1. THE CART SYSTEM (Products Only) ---

class Cart(models.Model):
    """Temporary holding area for physical items before checkout."""
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def get_cart_total(self):
        # Cart now exclusively handles products
        return sum(item.get_total for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    
    @property
    def get_total(self):
        price = self.variant.price_override if self.variant and self.variant.price_override else self.product.price
        return price * self.quantity


# --- 2. E-COMMERCE ORDER SYSTEM (Products) ---

def generate_order_ref():
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid - Awaiting Payment'),
        ('confirmed', 'Confirmed - Paid'),
        ('processing', 'Processing by Vendors'),
        ('shipped', 'Shipped / In Transit'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed & Verified'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    reference = models.CharField(max_length=20, unique=True, default=generate_order_ref)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    
    # Financial Snapshots
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Contact & Delivery
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    alt_phone = models.CharField(max_length=20, null=True, blank=True)
    whatsapp = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    street_address = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PAID', 'Paid - Awaiting Vendor'),
        ('ACCEPTED', 'Vendor Processing'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('RIDER_ASSIGNED', 'Rider Assigned'),
        ('PICKED_UP', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed & Paid Out'),
        ('CANCELLED', 'Cancelled')
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2) # Immutable price snapshot
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')
    
    # Logistics codes
    pickup_code = models.CharField(max_length=6, blank=True, null=True)
    delivery_code = models.CharField(max_length=6, blank=True, null=True)
    logistics_provider = models.CharField(max_length=50, default='GIGL')
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    rider_name = models.CharField(max_length=100, blank=True, null=True)


# --- 3. THE NEW SERVICE BOOKING ENGINE ---

class ServiceOrder(models.Model):
    class ServiceStatus(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Requested (Awaiting Provider)'
        QUOTE_SENT = 'QUOTE_SENT', 'Quote Sent (Awaiting Customer)'
        ACCEPTED = 'ACCEPTED', 'Accepted (Pending Payment)'
        PAID = 'PAID', 'Paid & Scheduled'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed (Pending Confirmation)'
        CONFIRMED = 'CONFIRMED', 'Confirmed & Closed'
        DECLINED = 'DECLINED', 'Declined by Provider'
        CANCELLED = 'CANCELLED', 'Cancelled'
        DISPUTED = 'DISPUTED', 'Disputed'

    # Core Relationships
    reference_code = models.CharField(max_length=50, unique=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='service_bookings')
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='received_bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, related_name='bookings')
    package = models.ForeignKey(ServicePackage, on_delete=models.SET_NULL, null=True, blank=True)

    # Fulfillment Details
    preferred_date = models.DateField()
    preferred_time = models.TimeField()
    service_location = models.TextField(help_text="The exact address where the service will be performed.")
    customer_notes = models.TextField(blank=True, help_text="Extra details or instructions for the provider.")

    # Financials
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="The locked-in price at the time of booking.")
    is_paid = models.BooleanField(default=False)
    paystack_reference = models.CharField(max_length=100, blank=True, null=True)

    # State Machine
    status = models.CharField(max_length=20, choices=ServiceStatus.choices, default=ServiceStatus.REQUESTED)
    
    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.reference_code:
            # Generates a unique tracking code like SRV-A1B2C3D4
            self.reference_code = f"SRV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference_code} - {self.service.name if self.service else 'Deleted Service'}"

class OrderMessage(models.Model):
    order = models.ForeignKey('ServiceOrder', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(blank=True, help_text="The text content of the message.")
    attachment = models.ImageField(upload_to='order_messages/', blank=True, null=True, help_text="Optional photo attachment.")
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at'] # Oldest messages at the top, newest at the bottom

    def __str__(self):
        return f"Message from {self.sender.username} on {self.order.reference_code}"


# --- 4. THE PAYMENT & ADDRESS SYSTEM ---

class PaymentAttempt(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('successful', 'Successful'),
        ('failed', 'Failed / Abandoned'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_attempts')
    reference = models.CharField(max_length=100, unique=True)
    
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True) 
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference} - {self.status}"

class ShippingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    alt_phone = models.CharField(max_length=20, blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True)
    region = models.CharField(max_length=100)
    street_address = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.street_address}, {self.region}"

class ServiceQuote(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Customer Approval'),
        ('ACCEPTED', 'Accepted & Paid'),
        ('REJECTED', 'Rejected by Customer'),
    )

    # Links directly to the existing service order
    order = models.OneToOneField('ServiceOrder', on_delete=models.CASCADE, related_name='quote')
    
    # Itemized costs
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    materials_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    
    # Context for the customer
    provider_notes = models.TextField(blank=True, null=True, help_text="Explain the costs to the customer.")
    valid_until = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Automatically calculate the total before saving
        self.total_amount = self.labor_cost + self.materials_cost
        
        # Set quote expiration to 3 days from creation if not provided
        if not self.valid_until:
            self.valid_until = timezone.now() + timedelta(days=3)
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Quote for Order #{self.order.id} - NGN {self.total_amount}"

class ServiceDispute(models.Model):
    class DisputeReason(models.TextChoices):
        NO_SHOW = 'NO_SHOW', 'Provider did not show up'
        POOR_QUALITY = 'POOR_QUALITY', 'Poor quality of work'
        INCOMPLETE = 'INCOMPLETE', 'Job was left incomplete'
        DAMAGE = 'DAMAGE', 'Property was damaged'
        OTHER = 'OTHER', 'Other issue'

    class DisputeStatus(models.TextChoices):
        OPEN = 'OPEN', 'Open (Under Review)'
        RESOLVED_REFUNDED = 'REFUNDED', 'Resolved (Refunded to Customer)'
        RESOLVED_RELEASED = 'RELEASED', 'Resolved (Funds Released to Provider)'

    order = models.OneToOneField('ServiceOrder', on_delete=models.CASCADE, related_name='dispute')
    reason = models.CharField(max_length=20, choices=DisputeReason.choices)
    description = models.TextField(help_text="Detailed explanation of the problem from the customer.")
    evidence = models.ImageField(upload_to='dispute_evidence/', blank=True, null=True, help_text="Optional photo proof.")
    status = models.CharField(max_length=20, choices=DisputeStatus.choices, default=DisputeStatus.OPEN)
    
    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for marketplace admins resolving this.")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute on {self.order.reference_code} - {self.get_status_display()}"