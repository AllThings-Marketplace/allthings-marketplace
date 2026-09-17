import uuid
import random
from django.db import models
from django.conf import settings
from marketplace.models import Product, Service, ProductVariant

# --- 1. THE CART SYSTEM ---

class Cart(models.Model):
    """Temporary holding area for items before checkout."""
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def get_cart_total(self):
        product_total = sum(item.get_total for item in self.items.all())
        service_total = sum(job.service.base_price for job in self.jobs.all() if job.service)
        return product_total + service_total

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    
    @property
    def get_total(self):
        price = self.variant.price_override if self.variant and self.variant.price_override else self.product.price
        return price * self.quantity

class CartJobBooking(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='jobs')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

# --- 2. THE ORDER SYSTEM ---

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

    # Contact & Delivery (Maintained from your original code)
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
    # Status choices remain specific to individual vendor fulfillment logic
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
    
    # Logistics codes (Maintained from your original code)
    pickup_code = models.CharField(max_length=6, blank=True, null=True)
    delivery_code = models.CharField(max_length=6, blank=True, null=True)
    logistics_provider = models.CharField(max_length=50, default='GIGL')
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    rider_name = models.CharField(max_length=100, blank=True, null=True)

class JobBooking(models.Model):
    class JobStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Assignment'
        ACCEPTED = 'ACCEPTED', 'Provider Assigned'
        IN_PROGRESS = 'IN_PROGRESS', 'Work In Progress'
        COMPLETED = 'COMPLETED', 'Job Completed'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='job_bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs')
    
    # NEW: Immutable price snapshot for services
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    service_address = models.TextField()
    order_note = models.TextField(null=True, blank=True)
    completion_code = models.CharField(max_length=6, blank=True, null=True)

# --- 3. THE PAYMENT SYSTEM ---

class PaymentAttempt(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('successful', 'Successful'),
        ('failed', 'Failed / Abandoned'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_attempts')
    reference = models.CharField(max_length=100, unique=True) # The Paystack transaction reference
    
    # NEW: Prevents duplicate webhook processing
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