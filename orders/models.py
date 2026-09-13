import uuid
import random
from django.db import models
from django.conf import settings
from marketplace.models import Product, Service

def generate_order_ref():
    # Generates a clean, unique 8-character string like 'ORD-A1B2C3D4'
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"

class Order(models.Model):
    # The parent container for the entire checkout
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    reference = models.CharField(max_length=20, unique=True, default=generate_order_ref)
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # --- New Contact & Delivery Fields ---
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    alt_phone = models.CharField(max_length=20, null=True, blank=True)
    whatsapp = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    street_address = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"

    @property
    def get_cart_total(self):
        # 1. Sum up all the physical products (price * quantity)
        product_total = sum(item.price * item.quantity for item in self.items.all())
        
        # 2. Sum up all the booked services (grabbing the base_price of the attached service)
        service_total = sum(job.service.base_price for job in self.job_bookings.all() if job.service)
        
        # 3. Add them together
        return product_total + service_total

class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('PAID', 'Paid - Awaiting Vendor'),
        ('ACCEPTED', 'Vendor Processing'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('RIDER_ASSIGNED', 'Rider Assigned'),
        ('PICKED_UP', 'In Transit'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed & Paid Out'),
        ('CANCELLED', 'Cancelled')
    ]
    
    # Relationships & Core Data
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('marketplace.Product', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    
    # State Machine & Tracking
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING_PAYMENT')
    
    # Logistics Security Codes
    pickup_code = models.CharField(max_length=6, blank=True, null=True)
    delivery_code = models.CharField(max_length=6, blank=True, null=True)

    logistics_provider = models.CharField(max_length=50, default='GIGL')
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    rider_name = models.CharField(max_length=100, blank=True, null=True)
    rider_phone = models.CharField(max_length=20, blank=True, null=True)

    # Add this inside your OrderItem class, right below the 'product' field:
    variant = models.ForeignKey('marketplace.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)

    # Update your __str__ method inside OrderItem to show the variant name if it exists:
    def __str__(self):
        product_name = self.product.name if self.product else "Deleted Product"
        if self.variant:
            product_name += f" ({self.variant.attribute_value})"
        return f"{self.quantity} x {product_name} (Order #{self.order.id})"

    @property
    def get_total(self):
        return self.price * self.quantity

    def generate_handshake_codes(self):
        """Generates secure 6-digit OTPs for rider pickup and customer delivery."""
        if not self.pickup_code or not self.delivery_code:
            self.pickup_code = self.pickup_code or str(random.randint(100000, 999999))
            self.delivery_code = self.delivery_code or str(random.randint(100000, 999999))
            # update_fields ensures we only hit the database for these two exact columns
            self.save(update_fields=['pickup_code', 'delivery_code'])

class JobBooking(models.Model):
    # Handles services scheduled within the order
    class JobStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Assignment'
        ACCEPTED = 'ACCEPTED', 'Provider Assigned'
        IN_PROGRESS = 'IN_PROGRESS', 'Work In Progress'
        COMPLETED = 'COMPLETED', 'Job Completed'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='job_bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    order_note = models.TextField(null=True, blank=True)
    completion_code = models.CharField(max_length=6, blank=True, null=True)

    def generate_completion_code(self):
        if not self.completion_code:
            self.completion_code = str(random.randint(100000, 999999))
            self.save(update_fields=['completion_code'])
    
    # Notice this links specifically to an assigned provider, left blank until someone accepts it!
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_jobs'
    )
    
    scheduled_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    service_address = models.TextField()
    
    # --- New Optional Note Field ---
    order_note = models.TextField(null=True, blank=True)

    def __str__(self):
        service_name = self.service.name if self.service else "Deleted Service"
        return f"{service_name} - {self.status}"

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