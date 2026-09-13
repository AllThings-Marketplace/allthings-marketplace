from django.contrib import admin
from .models import Order, OrderItem, JobBooking

# This allows us to see the products directly inside the Order page
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0 # Prevents Django from showing empty blank rows by default

# This allows us to see the service booking directly inside the Order page
class JobBookingInline(admin.StackedInline):
    model = JobBooking
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'is_paid', 'total_amount', 'created_at')
    list_filter = ('is_paid', 'created_at')
    # Here we attach the products and services to the main order view
    inlines = [OrderItemInline, JobBookingInline] 

@admin.register(JobBooking)
class JobBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'service', 'provider', 'status', 'scheduled_time')
    list_filter = ('status',)