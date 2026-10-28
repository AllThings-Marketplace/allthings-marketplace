import uuid
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from accounts.models import ProviderProfile
from .validators import validate_product_image


class PromoBanner(models.Model):
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    
    # Desktop vs Mobile Assets
    image = models.ImageField(upload_to='banners/', help_text="Desktop banner (e.g., 1920x600 layout)")
    mobile_image = models.ImageField(upload_to='banners/mobile/', null=True, blank=True, help_text="Mobile banner (e.g., 800x800 square or portrait layout).")
    
    link = models.CharField(max_length=255, blank=True, null=True, help_text="Where should this redirect when clicked?")
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title


class Category(models.Model):
    CATEGORY_TYPE_CHOICES = (
        ('PRODUCT', 'Physical Product Category'),
        ('SERVICE', 'Professional Service Category'),
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='subcategories',
        on_delete=models.CASCADE
    )
    category_type = models.CharField(
        max_length=15,
        choices=CATEGORY_TYPE_CHOICES,
        default='PRODUCT',
        db_index=True
    )
    search_keywords = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated keywords to auto-guess this category from product/service titles (e.g., wire, cable, coil, copper, mm)"
    )
    attribute_schema = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return f"[{self.get_category_type_display()}] {self.name}"


class Service(models.Model):
    class ServiceMode(models.TextChoices):
        REMOTE = 'REMOTE', 'Remote / Online'
        CUSTOMER_LOC = 'CUSTOMER_LOC', 'I travel to customer'
        PROVIDER_LOC = 'PROVIDER_LOC', 'Customer comes to me'
        BOTH = 'BOTH', 'Either location'

    class PricingType(models.TextChoices):
        FIXED = 'FIXED', 'Fixed Price'
        STARTING = 'STARTING', 'Starting From'
        HOURLY = 'HOURLY', 'Hourly Rate'
        QUOTE = 'QUOTE', 'Requires Custom Quote'
        PACKAGES = 'PACKAGES', 'Tiered Packages'

    class ServiceStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved (Public)'
        REJECTED = 'REJECTED', 'Rejected'

    provider = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='services')
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(help_text="Detailed description of the service and provider expertise.")
    
    # Fulfillment & Scope
    service_mode = models.CharField(max_length=20, choices=ServiceMode.choices, default=ServiceMode.CUSTOMER_LOC)
    service_radius_km = models.PositiveIntegerField(null=True, blank=True, help_text="How far are you willing to travel? (Leave blank if remote)")
    
    # Pricing Foundation
    pricing_type = models.CharField(max_length=20, choices=PricingType.choices, default=PricingType.FIXED)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Base/Starting price. Can be left blank if using Packages or Custom Quotes.")
    
    # Scope Details (Stored as JSON lists)
    whats_included = models.JSONField(default=list, blank=True, help_text="e.g., ['Initial inspection', 'Basic wiring', 'Cleanup']")
    whats_excluded = models.JSONField(default=list, blank=True, help_text="e.g., ['Replacement parts', 'Major structural work']")
    
    # Media
    cover_image = models.ImageField(upload_to='services/covers/', null=True, blank=True, help_text="The main banner image representing this service.")
    
    # State Machine & Moderation
    status = models.CharField(
        max_length=20,
        choices=ServiceStatus.choices,
        default=ServiceStatus.APPROVED
    )
    moderation_note = models.TextField(
        blank=True,
        help_text="Feedback for the provider if the service is held or rejected."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Service.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('marketplace:service_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return f"{self.name} - {self.provider.business_name if self.provider else 'Unknown Provider'}"


class ServicePackage(models.Model):
    """Handles the 'Basic', 'Standard', 'Premium' tiered pricing model."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100, help_text="e.g., Basic, Standard, Premium")
    description = models.TextField(blank=True, help_text="Short description of what this tier offers.")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_duration = models.CharField(max_length=100, help_text="e.g., '2-3 Hours', '1-2 Days'")
    features = models.JSONField(default=list, blank=True, help_text="List of specific features for this package.")

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.service.name} - {self.name} (NGN {self.price})"


class ServiceImage(models.Model):
    """Handles the provider's portfolio gallery (Before/After shots, previous work)."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='portfolio_images')
    image = models.ImageField(upload_to='services/portfolio/')
    caption = models.CharField(max_length=200, blank=True, help_text="e.g., 'Before and after of a full kitchen wiring job'")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Portfolio Image for {self.service.name}"


class Product(models.Model):
    class ProductStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved (Public)'
        REJECTED = 'REJECTED', 'Rejected'

    class ShippingClass(models.TextChoices):
        SMALL = 'SMALL', 'Small Parcel / Bike-Friendly (< 5kg — Bulbs, Switches, Tools)'
        MEDIUM = 'MEDIUM', 'Medium Box (5–20kg — Fans, Coils, Stabilizers)'
        HEAVY = 'HEAVY', 'Heavy / Bulky Cargo (> 20kg — Inverters, Solar Panels, Batteries)'

    # Relationships
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='products', null=True) 
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_count = models.IntegerField(default=0)
    description = models.TextField(blank=True)

    # --- Logistics & Package Sizing ---
    shipping_class = models.CharField(
        max_length=15,
        choices=ShippingClass.choices,
        default=ShippingClass.SMALL,
        help_text="Determines bike vs. van/cargo dispatch rates at checkout."
    )
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1.00,
        help_text="Estimated packaged weight in kg (per unit)."
    )
    
    # --- Image Validation Pipeline ---
    image = models.ImageField(
        upload_to='products/', 
        null=True, 
        blank=True,
        validators=[validate_product_image]
    )
    
    # --- Dynamic Attribute Storage ---
    attributes = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Dynamic specifications provided by the vendor."
    )

    # --- State Machine & Moderation ---
    status = models.CharField(
        max_length=20, 
        choices=ProductStatus.choices, 
        default=ProductStatus.DRAFT
    )
    moderation_note = models.TextField(
        blank=True, 
        help_text="Feedback for the vendor if the product is rejected."
    )
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Product.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('marketplace:product_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    STATUS_CHOICES = (
        ('UPLOADED', 'Uploaded'),
        ('PROCESSING', 'Processing'),
        ('APPROVED', 'Approved'),
        ('NEEDS_REVIEW', 'Needs Review'),
        ('REJECTED', 'Rejected'),
    )

    IMAGE_TYPE_CHOICES = (
        ('MAIN', 'Main Image'),
        ('GALLERY', 'Gallery Image'),
    )

    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='images')
    
    # Image Storage Fields
    original_image = models.ImageField(upload_to='products/original/')
    processed_image = models.ImageField(upload_to='products/processed/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='products/thumbnails/', null=True, blank=True)
    search_image = models.ImageField(upload_to='products/search/', null=True, blank=True)
    
    # Pipeline Metadata
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES, default='GALLERY')
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    rejection_reason = models.TextField(blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    
    # Display logic
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.get_image_type_display()} ({self.processing_status})"


class ProductVariant(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='variants')
    attribute_name = models.CharField(max_length=50, help_text="e.g., Color, Storage, Size")
    attribute_value = models.CharField(max_length=50, help_text="e.g., Blue, 256GB, XL")
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {self.attribute_value}"


class SavedItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='saved_by_users')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} saved {self.product.name}"


class ProviderInquiry(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_inquiries')
    provider = models.ForeignKey('accounts.ProviderProfile', on_delete=models.CASCADE, related_name='received_inquiries')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Inquiry from {self.sender.username} to {self.provider.business_name}"


class UserInteraction(models.Model):
    """
    The core event tracker for the recommendation engine. 
    Logs every meaningful action a user takes on the platform.
    """
    class InteractionType(models.TextChoices):
        VIEW = 'VIEW', 'Viewed'
        SEARCH = 'SEARCH', 'Searched'
        SAVE = 'SAVE', 'Saved to Wishlist'
        CART = 'CART', 'Added to Cart'
        PURCHASE = 'PURCHASE', 'Purchased'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interactions', null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices)
    weight = models.IntegerField(default=1, help_text="Algorithmic weight (e.g., View=1, Cart=8, Purchase=15)")
    
    search_query = models.CharField(max_length=255, null=True, blank=True, help_text="If they found this via search, what did they type?")
    duration_seconds = models.PositiveIntegerField(default=0, help_text="Time spent looking at the item (for future V2/V3 engine)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'interaction_type']),
            models.Index(fields=['session_key']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        actor = self.user.username if self.user else f"Guest ({self.session_key[:8]})"
        return f"{actor} {self.get_interaction_type_display()} {self.content_object}"


# ==============================================================================
# "REQUEST WHAT YOU NEED" — DEMAND DISCOVERY & SOURCING ENGINE
# ==============================================================================

class CustomerRequest(models.Model):
    class RequestType(models.TextChoices):
        PRODUCT = 'PRODUCT', 'Physical Product'
        SERVICE = 'SERVICE', 'Professional Service'

    class ProductCondition(models.TextChoices):
        NEW = 'NEW', 'Brand New'
        REFURBISHED = 'REFURBISHED', 'Refurbished / Foreign Used'
        USED = 'USED', 'Local Used'
        ANY = 'ANY', 'Any Condition'

    class RequestStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        MATCHING = 'MATCHING', 'Searching Vendors'
        MATCHED = 'MATCHED', 'Matches Found'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        CANCELLED = 'CANCELLED', 'Cancelled'

    reference = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_requests'
    )
    request_type = models.CharField(
        max_length=15,
        choices=RequestType.choices,
        default=RequestType.PRODUCT,
        db_index=True
    )
    title = models.CharField(max_length=220, help_text="Product name or service needed")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_requests'
    )

    # Product-specific optional fields
    brand = models.CharField(max_length=100, blank=True, help_text="Preferred brand (e.g., Havells, Coleman, Luminous)")
    specifications = models.CharField(max_length=255, blank=True, help_text="Model, capacity, gauge, or ratings")
    condition = models.CharField(
        max_length=20,
        choices=ProductCondition.choices,
        default=ProductCondition.NEW,
        blank=True
    )

    # Budget & Location fields
    budget_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    region = models.CharField(max_length=100, default='Rivers State', db_index=True)
    location_detail = models.CharField(max_length=200, blank=True, help_text="City, town, or neighborhood (e.g., Oyigbo, GRA)")
    preferred_date = models.DateField(null=True, blank=True, help_text="Preferred service date (if requesting a service)")
    description = models.TextField(blank=True, help_text="Additional context or project requirements")

    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['region', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            candidate = f"ATR-{year}-{uuid.uuid4().hex[:5].upper()}"
            while CustomerRequest.objects.filter(reference=candidate).exists():
                candidate = f"ATR-{year}-{uuid.uuid4().hex[:5].upper()}"
            self.reference = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('marketplace:request_detail', kwargs={'request_id': self.id})

    def __str__(self):
        return f"{self.reference} | [{self.get_request_type_display()}] {self.title}"


class RequestMatch(models.Model):
    class MatchSource(models.TextChoices):
        SYSTEM = 'SYSTEM', 'Instant Catalog Match'
        PROVIDER = 'PROVIDER', 'Verified Provider Offer'
        ADMIN = 'ADMIN', 'AllThings Sourcing Team'

    class MatchStatus(models.TextChoices):
        SUGGESTED = 'SUGGESTED', 'Suggested'
        ACCEPTED = 'ACCEPTED', 'Accepted by Customer'
        DISMISSED = 'DISMISSED', 'Dismissed'

    customer_request = models.ForeignKey(
        CustomerRequest,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    provider = models.ForeignKey(
        'accounts.ProviderProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='request_matches'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='request_matches'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='request_matches'
    )
    match_source = models.CharField(
        max_length=15,
        choices=MatchSource.choices,
        default=MatchSource.SYSTEM
    )
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=280, blank=True)
    status = models.CharField(
        max_length=15,
        choices=MatchStatus.choices,
        default=MatchStatus.SUGGESTED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-match_source', '-created_at']

    def __str__(self):
        target = self.product.name if self.product else (self.service.name if self.service else "Match")
        return f"Match for {self.customer_request.reference}: {target}"