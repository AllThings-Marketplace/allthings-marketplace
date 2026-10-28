from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from .models import (
    Category, Product, Service, PromoBanner,
    ProductImage, ProductVariant, ServicePackage,
    ServiceImage, ProviderInquiry, CustomerRequest, RequestMatch
)
from .views import _run_instant_catalog_matching


# --- 1. INLINES FOR PRODUCTS, SERVICES & CUSTOMER REQUESTS ---

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ('processing_status', 'is_approved')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ServicePackageInline(admin.TabularInline):
    model = ServicePackage
    extra = 1


class ServiceImageInline(admin.TabularInline):
    model = ServiceImage
    extra = 1


class RequestMatchInline(admin.TabularInline):
    model = RequestMatch
    extra = 1
    fields = ('match_source', 'provider', 'product', 'service', 'quoted_price', 'note', 'status')
    autocomplete_fields = ('product', 'service')


# --- 2. SHARED MODERATION ACTIONS ---

@admin.action(description="Approve selected listings (Set status=APPROVED & is_active=True)")
def approve_listings(modeladmin, request, queryset):
    queryset.update(status='APPROVED', is_active=True, moderation_note='')


@admin.action(description="Hold selected listings for review (Set status=PENDING & is_active=False)")
def hold_listings_for_review(modeladmin, request, queryset):
    queryset.update(status='PENDING', is_active=False)


# --- 3. MODEL ADMINS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'parent', 'is_active')
    list_filter = ('category_type', 'is_active', 'parent')
    list_editable = ('category_type', 'is_active')
    search_fields = ('name', 'search_keywords')
    fields = (
        'name',
        'slug',
        'category_type',
        'parent',
        'search_keywords',
        'attribute_schema',
        'is_active',
    )
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'provider',
        'category',
        'pricing_type',
        'base_price',
        'status',
        'is_active',
        'created_at',
    )
    list_filter = ('status', 'is_active', 'pricing_type', 'service_mode', 'category')
    list_editable = ('status', 'is_active')
    search_fields = ('name', 'provider__business_name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ServicePackageInline, ServiceImageInline]
    actions = [approve_listings, hold_listings_for_review]

    fieldsets = (
        ('Moderation & Visibility', {
            'fields': ('status', 'moderation_note', 'is_active'),
        }),
        ('Basic Information', {
            'fields': ('provider', 'category', 'name', 'slug', 'description', 'cover_image'),
        }),
        ('Fulfillment & Pricing', {
            'fields': ('service_mode', 'service_radius_km', 'pricing_type', 'base_price'),
        }),
        ('Scope of Work (Escrow Protection)', {
            'fields': ('whats_included', 'whats_excluded'),
            'description': 'Stored as JSON lists of included and excluded deliverables.',
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'provider',
        'category',
        'price',
        'stock_count',
        'shipping_class',
        'status',
        'is_active',
    )
    list_filter = ('status', 'is_active', 'shipping_class', 'category')
    list_editable = ('status', 'is_active', 'shipping_class')
    search_fields = ('name', 'provider__business_name', 'description')
    inlines = [ProductImageInline, ProductVariantInline]
    prepopulated_fields = {'slug': ('name',)}
    actions = [approve_listings, hold_listings_for_review]

    fieldsets = (
        ('Moderation & Status', {
            'fields': ('status', 'moderation_note', 'is_active'),
        }),
        ('Basic Information', {
            'fields': ('provider', 'category', 'name', 'slug', 'description', 'price', 'stock_count', 'image'),
        }),
        ('Logistics & Package Sizing', {
            'fields': ('shipping_class', 'weight_kg'),
            'description': 'Used by LogisticsEngine to calculate bike vs. van dispatch rates at checkout.',
        }),
        ('Dynamic Specifications', {
            'fields': ('attributes',),
            'description': 'Category-specific details (e.g., {"Cable Gauge (mm²)": "2.5mm", "Brand": "Coleman"}).',
        }),
    )


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'display_order')
    list_editable = ('is_active', 'display_order')
    list_filter = ('is_active',)
    fields = (
        'title', 
        'subtitle', 
        'image', 
        'mobile_image', 
        'link', 
        'is_active', 
        'display_order',
    )


@admin.register(ProviderInquiry)
class ProviderInquiryAdmin(admin.ModelAdmin):
    list_display = ('sender', 'provider', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'provider__business_name', 'message')


# --- 4. "REQUEST WHAT YOU NEED" — SOURCING & DEMAND ANALYTICS ADMIN ---

@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'title',
        'request_type',
        'customer',
        'category',
        'region',
        'budget_max',
        'status',
        'match_count_display',
        'created_at',
    )
    list_filter = ('request_type', 'status', 'region', 'condition', 'category', 'created_at')
    list_editable = ('status',)
    search_fields = (
        'reference',
        'title',
        'brand',
        'specifications',
        'location_detail',
        'description',
        'customer__username',
        'customer__email',
    )
    readonly_fields = ('reference', 'created_at', 'updated_at')
    inlines = [RequestMatchInline]
    actions = ['run_catalog_matcher', 'mark_requests_matching', 'mark_requests_fulfilled']

    fieldsets = (
        ('Request Tracking & Status', {
            'fields': ('reference', 'customer', 'request_type', 'status', 'created_at', 'updated_at'),
        }),
        ('What the Customer Needs', {
            'fields': ('title', 'category', 'brand', 'specifications', 'condition', 'description'),
        }),
        ('Budget, Location & Schedule', {
            'fields': ('budget_min', 'budget_max', 'region', 'location_detail', 'preferred_date'),
        }),
    )

    def match_count_display(self, obj):
        return obj.matches.count()
    match_count_display.short_description = 'Matches'

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        new_matches_added = False
        for instance in instances:
            if isinstance(instance, RequestMatch):
                if not instance.pk:
                    new_matches_added = True
                if not instance.provider:
                    if instance.product and instance.product.provider:
                        instance.provider = instance.product.provider
                    elif instance.service and instance.service.provider:
                        instance.provider = instance.service.provider
                if not instance.quoted_price:
                    if instance.product:
                        instance.quoted_price = instance.product.price
                    elif instance.service:
                        instance.quoted_price = instance.service.base_price
            instance.save()
        formset.save_m2m()

        for obj in formset.deleted_objects:
            obj.delete()

        # If admin attached a new match, flip status to MATCHED and notify the customer
        if new_matches_added:
            cust_req = form.instance
            if cust_req.status in ['PENDING', 'MATCHING']:
                cust_req.status = CustomerRequest.RequestStatus.MATCHED
                cust_req.save(update_fields=['status', 'updated_at'])
            try:
                from notifications.models import Notification
                ct = ContentType.objects.get_for_model(cust_req)
                Notification.objects.create(
                    recipient=cust_req.customer,
                    notification_type='ORDER',
                    title=f"We Found a Match for {cust_req.reference}!",
                    message=f"Good news! Our sourcing team matched a listing to your request for '{cust_req.title}'.",
                    content_type=ct,
                    object_id=cust_req.id,
                )
            except Exception:
                pass

    @admin.action(description="1. Run Instant Catalog Matcher on selected requests")
    def run_catalog_matcher(self, request, queryset):
        total_found = 0
        for req_obj in queryset:
            total_found += _run_instant_catalog_matching(req_obj)
        self.message_user(
            request,
            f"Catalog scan complete! Attached {total_found} match(es) across {queryset.count()} request(s).",
            messages.SUCCESS
        )

    @admin.action(description="2. Mark selected requests as Searching Vendors (MATCHING)")
    def mark_requests_matching(self, request, queryset):
        updated = queryset.update(status=CustomerRequest.RequestStatus.MATCHING)
        self.message_user(request, f"Marked {updated} request(s) as Searching Vendors.", messages.INFO)

    @admin.action(description="3. Mark selected requests as FULFILLED")
    def mark_requests_fulfilled(self, request, queryset):
        updated = queryset.update(status=CustomerRequest.RequestStatus.FULFILLED)
        self.message_user(request, f"Marked {updated} request(s) as Fulfilled.", messages.SUCCESS)


@admin.register(RequestMatch)
class RequestMatchAdmin(admin.ModelAdmin):
    list_display = (
        'customer_request',
        'match_source',
        'provider',
        'product',
        'service',
        'quoted_price',
        'status',
        'created_at',
    )
    list_filter = ('match_source', 'status', 'created_at')
    search_fields = (
        'customer_request__reference',
        'customer_request__title',
        'provider__business_name',
        'product__name',
        'service__name',
    )