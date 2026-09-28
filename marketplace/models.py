from django.conf import settings
from django.db import models
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
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    is_active = models.BooleanField(default=True)
    
    # --- NEW: Dynamic Attribute Schema ---
    attribute_schema = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Define required fields. Format: [{'name': 'RAM'}, {'name': 'Processor'}]"
    )

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        # Shows the hierarchy in your Django admin (e.g., "Gadgets -> Audio")
        if self.parent:
            return f"{self.parent.name} -> {self.name}"
        return self.name

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

    # The missing link: Assigning the service to a specific vendor/provider
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

    # Relationships
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name='products', null=True) 
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    
    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_count = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    
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

    # Relationship to the main product
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
        # Ensures a user cannot save the same product twice
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