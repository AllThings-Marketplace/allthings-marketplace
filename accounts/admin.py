from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.html import format_html

from .models import User, ProviderProfile, VendorWallet, VendorTransaction, ContactOTP


def _notify_provider_kyc(provider, title, message):
    """Sends an in-app Bell & Email notification to the provider when KYC status changes."""
    if not provider or not provider.user:
        return
    try:
        from notifications.models import Notification
        ct = ContentType.objects.get_for_model(provider)
        Notification.objects.create(
            recipient=provider.user,
            notification_type='SYSTEM',
            title=title,
            message=message,
            content_type=ct,
            object_id=provider.id,
        )
    except Exception:
        pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'is_verified', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')

    fieldsets = UserAdmin.fieldsets + (
        ('Platform Role & Contact', {
            'fields': ('role', 'phone_number', 'is_verified'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Role & Contact', {
            'fields': ('role', 'phone_number', 'is_verified'),
        }),
    )


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'user',
        'provider_type',
        'verification_status',
        'email_verified',
        'phone_verified',
        'trust_score',
        'region',
        'applied_at',
    )
    list_filter = (
        'verification_status',
        'provider_type',
        'email_verified',
        'phone_verified',
        'region',
    )
    list_editable = ('verification_status', 'trust_score')
    search_fields = ('business_name', 'user__username', 'user__email', 'phone', 'cac_registration_number')
    readonly_fields = (
        'applied_at',
        'approved_at',
        'id_document_preview',
        'selfie_preview',
        'exterior_preview',
        'interior_preview',
        'google_maps_link',
    )
    actions = ['approve_provider_kyc', 'activate_provider_accounts', 'flag_providers_for_review']

    fieldsets = (
        ('Moderation & Trust Gate', {
            'fields': (
                'verification_status',
                'trust_score',
                'email_verified',
                'phone_verified',
                'applied_at',
                'approved_at',
            ),
        }),
        ('Stage 1: Personal & Business Identity', {
            'fields': (
                'user',
                'business_name',
                'provider_type',
                'business_category',
                'phone',
                'dob',
                'residential_address',
            ),
        }),
        ('Stage 2: Government ID & Live Selfie (KYC)', {
            'fields': (
                'id_type',
                'id_document',
                'id_document_preview',
                'selfie_image',
                'selfie_preview',
            ),
        }),
        ('Stage 3: Business Registration', {
            'fields': (
                'business_description',
                'cac_registration_number',
                'business_certificate',
            ),
        }),
        ('Stage 4: Physical Store Location & GPS', {
            'fields': (
                'region',
                'store_address',
                'latitude',
                'longitude',
                'google_maps_link',
                'exterior_image',
                'exterior_preview',
                'interior_image',
                'interior_preview',
                'signboard_image',
            ),
        }),
        ('Stage 5: Verified Paystack Settlement Bank', {
            'fields': (
                'bank_name',
                'bank_code',
                'account_number',
                'account_name',
            ),
        }),
    )

    # --- Media & Map Previews ---
    def _render_image_preview(self, image_field, label="Document"):
        if image_field and hasattr(image_field, 'url'):
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" alt="{}" style="max-height: 160px; border-radius: 8px; border: 1px solid #cbd5e1; padding: 4px; background: #fff;" />'
                '</a>',
                image_field.url,
                image_field.url,
                label,
            )
        return "No file uploaded"

    def id_document_preview(self, obj):
        return self._render_image_preview(obj.id_document, "Government ID")
    id_document_preview.short_description = "ID Document Preview"

    def selfie_preview(self, obj):
        return self._render_image_preview(obj.selfie_image, "Live Selfie")
    selfie_preview.short_description = "Live Selfie Preview"

    def exterior_preview(self, obj):
        return self._render_image_preview(obj.exterior_image, "Shop Exterior")
    exterior_preview.short_description = "Exterior Photo Preview"

    def interior_preview(self, obj):
        return self._render_image_preview(obj.interior_image, "Shop Interior")
    interior_preview.short_description = "Interior Photo Preview"

    def google_maps_link(self, obj):
        if obj.latitude and obj.longitude:
            url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '<a href="{}" target="_blank" style="font-weight: 700; color: #2563eb;">'
                '📍 View Pinned GPS Location ({}, {}) on Google Maps &rarr;'
                '</a>',
                url,
                obj.latitude,
                obj.longitude,
            )
        return "GPS coordinates not captured yet"
    google_maps_link.short_description = "Satellite Map Pin"

    # --- Single-Save Hook ---
    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = ProviderProfile.objects.filter(pk=obj.pk).values_list('verification_status', flat=True).first()

        if obj.verification_status in ['APPROVED', 'ACTIVE'] and not obj.approved_at:
            obj.approved_at = timezone.now()

        super().save_model(request, obj, form, change)

        if obj.verification_status in ['APPROVED', 'ACTIVE']:
            obj.user.role = User.Role.PROVIDER
            obj.user.is_verified = True
            obj.user.save(update_fields=['role', 'is_verified'])
            VendorWallet.objects.get_or_create(provider=obj)

        if previous_status != obj.verification_status:
            if obj.verification_status == 'APPROVED':
                _notify_provider_kyc(
                    obj,
                    title="KYC Approved! Complete Your Bank Setup",
                    message=f"Congratulations! Your KYC for '{obj.business_name}' has been approved. Link your bank account to activate your storefront.",
                )
            elif obj.verification_status == 'ACTIVE':
                _notify_provider_kyc(
                    obj,
                    title=f"{obj.business_name} is Now Live!",
                    message="Your provider account is fully active. You can now publish listings and receive escrow payouts.",
                )

    # --- 1-Click Bulk Admin Actions ---
    @admin.action(description="1. Approve KYC (Set APPROVED & unlock Stage 5 Bank Setup)")
    def approve_provider_kyc(self, request, queryset):
        now = timezone.now()
        count = 0
        for profile in queryset.select_related('user'):
            profile.verification_status = ProviderProfile.VerificationPhase.APPROVED
            profile.approved_at = profile.approved_at or now
            profile.save(update_fields=['verification_status', 'approved_at'])

            profile.user.role = User.Role.PROVIDER
            profile.user.is_verified = True
            profile.user.save(update_fields=['role', 'is_verified'])
            VendorWallet.objects.get_or_create(provider=profile)

            _notify_provider_kyc(
                profile,
                title="KYC Approved! Link Your Payout Bank",
                message=f"Your verification for '{profile.business_name}' has been approved! Visit your Provider Verification page to link your bank account.",
            )
            count += 1

        self.message_user(request, f"Approved KYC for {count} provider(s) and sent notifications.", messages.SUCCESS)

    @admin.action(description="2. Fully Activate Providers (Set ACTIVE & ensure Wallet exists)")
    def activate_provider_accounts(self, request, queryset):
        now = timezone.now()
        count = 0
        for profile in queryset.select_related('user'):
            profile.verification_status = ProviderProfile.VerificationPhase.ACTIVE
            profile.approved_at = profile.approved_at or now
            if profile.trust_score < 70:
                profile.trust_score = 70
            profile.save(update_fields=['verification_status', 'approved_at', 'trust_score'])

            profile.user.role = User.Role.PROVIDER
            profile.user.is_verified = True
            profile.user.save(update_fields=['role', 'is_verified'])
            VendorWallet.objects.get_or_create(provider=profile)

            _notify_provider_kyc(
                profile,
                title=f"{profile.business_name} is Now Fully Active!",
                message="Your provider portal is unlocked. You can now add products and services.",
            )
            count += 1

        self.message_user(request, f"Activated {count} provider account(s).", messages.SUCCESS)

    @admin.action(description="3. Flag selected providers for compliance review")
    def flag_providers_for_review(self, request, queryset):
        updated = queryset.update(verification_status=ProviderProfile.VerificationPhase.FLAGGED)
        self.message_user(request, f"Flagged {updated} provider(s) for review.", messages.WARNING)


@admin.register(VendorWallet)
class VendorWalletAdmin(admin.ModelAdmin):
    list_display = ('provider', 'available_balance', 'pending_balance', 'total_withdrawn', 'last_updated')
    search_fields = ('provider__business_name', 'provider__user__email')
    readonly_fields = ('last_updated',)


@admin.register(VendorTransaction)
class VendorTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'get_provider_name', 'get_bank_details', 'transaction_type', 'net_amount', 'status', 'created_at')
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = ('reference', 'wallet__provider__business_name', 'wallet__provider__account_number')
    readonly_fields = ('reference', 'wallet', 'transaction_type', 'gross_amount', 'commission', 'net_amount')
    actions = ['mark_payouts_completed']

    def get_provider_name(self, obj):
        return obj.wallet.provider.business_name
    get_provider_name.short_description = 'Business'

    def get_bank_details(self, obj):
        provider = obj.wallet.provider
        if obj.transaction_type == 'PAYOUT':
            return f"{provider.bank_name} - {provider.account_number}"
        return "-"
    get_bank_details.short_description = 'Bank Details'

    @admin.action(description="Mark selected payouts as COMPLETED")
    def mark_payouts_completed(self, request, queryset):
        pending_payouts = queryset.filter(transaction_type='PAYOUT', status='PENDING')
        updated_count = pending_payouts.update(status='COMPLETED', cleared_at=timezone.now())
        self.message_user(
            request,
            f"Successfully marked {updated_count} payout(s) as COMPLETED.",
            messages.SUCCESS,
        )


@admin.register(ContactOTP)
class ContactOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'target', 'code', 'is_verified', 'attempts', 'created_at', 'expires_at')
    list_filter = ('channel', 'is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'target', 'code')
    readonly_fields = ('created_at', 'verified_at')