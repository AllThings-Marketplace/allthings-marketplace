from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from .models import User, ProviderProfile, VendorWallet, VendorTransaction

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # 1. The columns shown on the main list of users
    list_display = ('username', 'email', 'role', 'phone_number', 'is_staff')
    
    # 2. The filter options on the right sidebar
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    
    # 3. Adds a search bar for finding specific users
    search_fields = ('username', 'email', 'phone_number')
    
    # 4. Adding our custom fields to the screen when you EDIT an existing user
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Details', {
            'fields': ('role', 'phone_number'),
        }),
    )
    
    # 5. Adding our custom fields to the screen when you CREATE a new user manually
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Details', {
            'fields': ('role', 'phone_number'),
        }),
    )

@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'provider_type', 'verification_status', 'applied_at')
    list_filter = ('verification_status', 'provider_type')
    search_fields = ('business_name', 'user__email')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

# Registering the financial models for admin oversight
admin.site.register(VendorWallet)

@admin.register(VendorTransaction)
class VendorTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'get_provider_name', 'get_bank_details', 'transaction_type', 'net_amount', 'status', 'created_at')
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = ('reference', 'wallet__provider__business_name', 'wallet__provider__account_number')
    readonly_fields = ('reference', 'wallet', 'transaction_type', 'gross_amount', 'commission', 'net_amount')
    
    # Custom action to mark payouts as fulfilled
    actions = ['mark_payouts_completed']

    def get_provider_name(self, obj):
        return obj.wallet.provider.business_name
    get_provider_name.short_description = 'Business'

    def get_bank_details(self, obj):
        # Pulls the verified bank details directly into the list view
        provider = obj.wallet.provider
        if obj.transaction_type == 'PAYOUT':
            return f"{provider.bank_name} - {provider.account_number}"
        return "-"
    get_bank_details.short_description = 'Bank Details'

    @admin.action(description="Mark selected payouts as COMPLETED")
    def mark_payouts_completed(self, request, queryset):
        # Only affect PENDING payouts to prevent accidental edits to sales records
        pending_payouts = queryset.filter(transaction_type='PAYOUT', status='PENDING')
        updated_count = pending_payouts.update(status='COMPLETED')
        
        self.message_user(
            request, 
            f"Successfully marked {updated_count} payout(s) as COMPLETED.", 
            messages.SUCCESS
        )