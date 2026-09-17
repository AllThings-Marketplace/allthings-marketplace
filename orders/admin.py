from django.contrib import admin
from .models import Order, OrderItem, JobBooking, Cart, CartItem, CartJobBooking, PaymentAttempt, ShippingAddress

# --- INLINES ---
# These allow us to see child items directly inside the parent page
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class JobBookingInline(admin.StackedInline):
    model = JobBooking
    extra = 0

class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

class CartJobBookingInline(admin.TabularInline):
    model = CartJobBooking
    extra = 0


# --- ADMIN MODELS ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Updated: Replaced 'is_paid' with 'status'
    list_display = ('id', 'reference', 'customer', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reference', 'customer__username', 'customer__email')
    # Added PaymentAttemptInline so you can see failed/successful payments directly on the order
    inlines = [OrderItemInline, JobBookingInline, PaymentAttemptInline] 

@admin.register(JobBooking)
class JobBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'provider', 'status', 'scheduled_time')
    list_filter = ('status',)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'created_at', 'updated_at')
    inlines = [CartItemInline, CartJobBookingInline]

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