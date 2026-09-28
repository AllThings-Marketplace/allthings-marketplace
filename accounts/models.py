from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Define our three core roles
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        PROVIDER = 'PROVIDER', 'Provider'
        ADMIN = 'ADMIN', 'Admin'
    
    # Custom fields
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CUSTOMER)
    is_verified = models.BooleanField(default=False) # Admins will toggle this for electricians
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} - {self.role}"

class ProviderProfile(models.Model):
    class ProviderType(models.TextChoices):
        VENDOR = 'VENDOR', 'Retail Vendor (Products)'
        SERVICE = 'SERVICE', 'Service Professional'
        BOTH = 'BOTH', 'Both (Products & Services)'
        
    class IDType(models.TextChoices):
        NIN = 'NIN', 'NIN Slip / Card'
        DRIVERS = 'DRIVERS', "Driver's License"
        PASSPORT = 'PASSPORT', 'International Passport'
        VOTERS = 'VOTERS', "Voter's Card"

    class VerificationPhase(models.TextChoices):
        STAGE_1_BASIC = 'STAGE_1_BASIC', 'Basic Details Complete'
        STAGE_2_KYC = 'STAGE_2_KYC', 'KYC Complete'
        STAGE_3_BUSINESS = 'STAGE_3_BUSINESS', 'Business Details Complete'
        STAGE_4_LOCATION = 'STAGE_4_LOCATION', 'Location Complete (Under Review)'
        APPROVED = 'APPROVED', 'Approved (Pending Payout)'
        ACTIVE = 'ACTIVE', 'Fully Active'
        FLAGGED = 'FLAGGED', 'Flagged for Review'

    # Core Link
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='provider_profile')
    
    # SCREEN 1: Basic Information
    business_name = models.CharField(max_length=150)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    business_category = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20)
    dob = models.DateField(null=True, blank=True)
    residential_address = models.TextField(null=True, blank=True)
    
    # SCREEN 2: Identity (KYC)
    id_type = models.CharField(max_length=20, choices=IDType.choices, null=True, blank=True)
    id_document = models.ImageField(upload_to='provider_kyc/id/', null=True, blank=True)
    selfie_image = models.ImageField(upload_to='provider_kyc/selfie/', null=True, blank=True)
    
    # SCREEN 3: Business Verification
    business_description = models.TextField(null=True, blank=True)
    cac_registration_number = models.CharField(max_length=50, null=True, blank=True)
    business_certificate = models.FileField(upload_to='provider_business/certs/', null=True, blank=True)
    
    # SCREEN 4: Location Verification
    region = models.CharField(max_length=100, null=True, blank=True)
    store_address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    exterior_image = models.ImageField(upload_to='provider_location/exterior/', null=True, blank=True)
    interior_image = models.ImageField(upload_to='provider_location/interior/', null=True, blank=True)
    signboard_image = models.ImageField(upload_to='provider_location/signboard/', null=True, blank=True)
    
    # SCREEN 5: Payouts (Unlocked post-approval)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    bank_code = models.CharField(max_length=10, null=True, blank=True, help_text="The 3-digit Paystack bank code")
    account_name = models.CharField(max_length=150, null=True, blank=True)
    
    # System Tracking
    verification_status = models.CharField(max_length=30, choices=VerificationPhase.choices, default=VerificationPhase.STAGE_1_BASIC)
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    trust_score = models.IntegerField(
        default=50, 
        help_text="0-100 score. High scores can auto-approve products. Low scores flag for manual review."
    )

    def __str__(self):
        return f"{self.business_name} - {self.get_verification_status_display()}"

class VendorWallet(models.Model):
    # Strictly tied to the provider, automatically created upon approval
    provider = models.OneToOneField(ProviderProfile, on_delete=models.CASCADE, related_name='wallet')
    
    # Escrow Funds (Order paid, but not yet delivered/completed)
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Cleared Funds (Ready for Paystack transfer)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Lifetime Earnings Tracker
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.provider.business_name} Wallet - Available: NGN {self.available_balance}"

class VendorTransaction(models.Model):
    class TransactionType(models.TextChoices):
        SALE = 'SALE', 'Product/Service Sale'
        PAYOUT = 'PAYOUT', 'Bank Payout'
        REFUND = 'REFUND', 'Customer Refund'

    class TransactionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Settlement'
        CLEARED = 'CLEARED', 'Cleared to Available Balance'
        COMPLETED = 'COMPLETED', 'Successfully Paid Out'
        FAILED = 'FAILED', 'Transaction Failed'

    wallet = models.ForeignKey(VendorWallet, on_delete=models.CASCADE, related_name='transactions')
    
    # Lazy reference to 'orders.Order' prevents circular import crashes
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    
    # The Financial Breakdown
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total paid by customer")
    commission = models.DecimalField(max_digits=12, decimal_places=2, help_text="Platform fee (e.g., 10%)")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount vendor actually receives")
    
    reference = models.CharField(max_length=100, unique=True, help_text="Paystack ref or internal ID")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    
    created_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.status} - NGN {self.net_amount}"

class Follower(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    provider = models.ForeignKey('ProviderProfile', on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can only follow a specific provider once
        unique_together = ('user', 'provider')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} follows {self.provider.business_name}"