from django.contrib import admin
from .models import Order, OrderItem, Cart, CartItem, PaymentAttempt, ShippingAddress, ServiceOrder, ServiceDispute

# --- INLINES ---
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

# --- ADMIN MODELS ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'customer', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reference', 'customer__username', 'customer__email')
    inlines = [OrderItemInline, PaymentAttemptInline] 

@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'service', 'customer', 'provider', 'status', 'preferred_date')
    list_filter = ('status', 'created_at', 'preferred_date')
    search_fields = ('reference_code', 'customer__username', 'provider__user__username', 'service__name')
    readonly_fields = ('reference_code', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Core Details', {
            'fields': ('reference_code', 'customer', 'provider', 'service', 'package', 'status')
        }),
        ('Fulfillment', {
            'fields': ('preferred_date', 'preferred_time', 'service_location', 'customer_notes')
        }),
        ('Financials', {
            'fields': ('agreed_price', 'is_paid', 'paystack_reference')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ServiceDispute)
class ServiceDisputeAdmin(admin.ModelAdmin):
    list_display = ('order', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('order__reference_code', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'created_at', 'updated_at')
    inlines = [CartItemInline]

@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('reference', 'order', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reference', 'order__reference')

@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'phone', 'region', 'is_default')
    list_filter = ('is_default', 'region')
    search_fields = ('user__username', 'phone')