from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Order, OrderItem, Cart, CartItem, PaymentAttempt, 
    ShippingAddress, ServiceOrder, ServiceDispute,
    SupportTicket, TicketMessage
)

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

class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('sender', 'body', 'attachment', 'is_staff_reply', 'is_read', 'created_at')

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

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_reference', 'user', 'category', 'priority', 
        'status', 'created_at', 'arbitration_console_link'
    )
    list_filter = ('status', 'priority', 'category', 'created_at')
    search_fields = (
        'ticket_reference', 'subject', 'description', 
        'user__username', 'user__email', 
        'order__reference', 'service_order__reference_code'
    )
    readonly_fields = ('ticket_reference', 'created_at', 'updated_at', 'resolved_at')
    inlines = [TicketMessageInline]

    fieldsets = (
        ('Ticket Overview', {
            'fields': ('ticket_reference', 'user', 'category', 'priority', 'status')
        }),
        ('Contextual Escrow & Order Links', {
            'fields': ('order', 'order_item', 'service_order', 'payment_attempt')
        }),
        ('Issue & Resolution Details', {
            'fields': ('subject', 'description', 'evidence', 'resolution_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )

    def arbitration_console_link(self, obj):
        url = reverse('orders:ticket_detail', args=[obj.ticket_reference])
        return format_html(
            '<a href="{}" style="background: #2563eb; color: #fff; padding: 4px 10px; '
            'border-radius: 6px; font-weight: 600; font-size: 12px; text-decoration: none;">'
            'Arbitrate / Reply</a>',
            url
        )
    arbitration_console_link.short_description = 'Live Console'

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