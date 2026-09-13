from django.contrib import admin
from .models import Category, Product, Service, PromoBanner, ProductImage, ProductVariant

# --- New Inlines for Gallery & Variants ---
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    fields = ('name', 'slug', 'parent', 'is_active', 'attribute_schema')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_price', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',) # Adds a search bar for services

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Added 'provider' and 'status' for better visibility in the main list
    list_display = ('name', 'provider', 'category', 'price', 'status', 'is_active')
    list_filter = ('status', 'category', 'is_active')
    search_fields = ('name', 'provider__business_name') 
    
    inlines = [ProductImageInline, ProductVariantInline]
    prepopulated_fields = {'slug': ('name',)}

    # Reorganized fieldsets to include the Moderation section
    fieldsets = (
        ('Moderation & Status', {
            'fields': ('status', 'moderation_note', 'is_active'),
            'classes': ('collapse',), # Collapses this section by default to keep the UI clean
        }),
        ('Basic Information', {
            'fields': ('provider', 'category', 'name', 'slug', 'description', 'price', 'stock_count', 'image')
        }),
        ('Dynamic Specifications', {
            'fields': ('attributes',),
            'description': 'Category-specific details (e.g., RAM, Material, Brand). Must be valid JSON format, e.g., {"RAM": "16GB", "Brand": "Sony"}.'
        }),
    )

@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'display_order')
    list_editable = ('is_active', 'display_order')
    list_filter = ('is_active',)
    
    # Controls the order of the fields on the edit page
    fields = (
        'title', 
        'subtitle', 
        'image', 
        'mobile_image', 
        'link', 
        'is_active', 
        'display_order'
    )