import os
import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from marketplace.validators import (
    validate_product_image as _raw_validate_product_image,
    validate_kyc_document as _raw_validate_kyc_document,
)


def validate_product_image(file_obj):
    """Only run image validation on newly uploaded files, not existing Cloudinary Public IDs."""
    if not file_obj or getattr(file_obj, '_committed', False):
        return
    if not isinstance(file_obj, UploadedFile) and not isinstance(getattr(file_obj, '_file', None), UploadedFile):
        return
    return _raw_validate_product_image(file_obj)


def validate_kyc_document(file_obj, allow_pdf=True):
    """Only run KYC document validation on newly uploaded files, not existing Cloudinary Public IDs."""
    if not file_obj or getattr(file_obj, '_committed', False):
        return
    if not isinstance(file_obj, UploadedFile) and not isinstance(getattr(file_obj, '_file', None), UploadedFile):
        return
    return _raw_validate_kyc_document(file_obj, allow_pdf=allow_pdf)


def kyc_id_upload_path(instance, filename):
    ext = os.path.splitext(filename or '')[1].lower() or '.jpg'
    return f"private_kyc/id/user_{instance.user_id}_{uuid.uuid4().hex}{ext}"


def kyc_selfie_upload_path(instance, filename):
    ext = os.path.splitext(filename or '')[1].lower() or '.jpg'
    return f"private_kyc/selfie/user_{instance.user_id}_{uuid.uuid4().hex}{ext}"


def kyc_cert_upload_path(instance, filename):
    ext = os.path.splitext(filename or '')[1].lower() or '.pdf'
    return f"private_kyc/certs/user_{instance.user_id}_{uuid.uuid4().hex}{ext}"


def store_location_upload_path(instance, filename):
    ext = os.path.splitext(filename or '')[1].lower() or '.jpg'
    return f"provider_location/user_{instance.user_id}_{uuid.uuid4().hex}{ext}"


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        PROVIDER = 'PROVIDER', 'Provider'
        ADMIN = 'ADMIN', 'Admin'
    
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.CUSTOMER)
    is_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.username} - {self.role}"


class ContactOTP(models.Model):
    """
    Stores time-bound, rate-limited 6-digit OTPs for inline Email and Phone
    verification during Provider Onboarding.
    """
    class Channel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email Address'
        PHONE = 'PHONE', 'Phone Number (SMS)'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contact_otps'
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    target = models.CharField(max_length=150, db_index=True, help_text="Normalized email or phone number")
    code = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'channel', 'target']),
        ]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        status = "Verified" if self.is_verified else "Pending"
        return f"{self.user.username} - {self.channel} ({self.target}) [{status}]"


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
    
    # SCREEN 1: Basic Information & Verified Contact Flags
    business_name = models.CharField(max_length=150)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    business_category = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=20)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    dob = models.DateField(null=True, blank=True)
    residential_address = models.TextField(null=True, blank=True)
    
    # SCREEN 2: Identity (KYC) - Randomized UUID paths & strict validators
    id_type = models.CharField(max_length=20, choices=IDType.choices, null=True, blank=True)
    id_document = models.FileField(
        upload_to=kyc_id_upload_path,
        null=True,
        blank=True,
        validators=[validate_kyc_document]
    )
    selfie_image = models.ImageField(
        upload_to=kyc_selfie_upload_path,
        null=True,
        blank=True,
        validators=[validate_product_image]
    )
    
    # SCREEN 3: Business Verification
    business_description = models.TextField(null=True, blank=True)
    cac_registration_number = models.CharField(max_length=50, null=True, blank=True)
    business_certificate = models.FileField(
        upload_to=kyc_cert_upload_path,
        null=True,
        blank=True,
        validators=[validate_kyc_document]
    )
    
    # SCREEN 4: Location Verification
    region = models.CharField(max_length=100, null=True, blank=True)
    store_address = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    exterior_image = models.ImageField(
        upload_to=store_location_upload_path,
        null=True,
        blank=True,
        validators=[validate_product_image]
    )
    interior_image = models.ImageField(
        upload_to=store_location_upload_path,
        null=True,
        blank=True,
        validators=[validate_product_image]
    )
    signboard_image = models.ImageField(
        upload_to=store_location_upload_path,
        null=True,
        blank=True,
        validators=[validate_product_image]
    )
    
    # SCREEN 5: Payouts (Unlocked post-approval)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    bank_code = models.CharField(max_length=10, null=True, blank=True, help_text="The 3-digit Paystack bank code")
    account_name = models.CharField(max_length=150, null=True, blank=True)
    
    # System Tracking & Spot-Flagging
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationPhase.choices,
        default=VerificationPhase.STAGE_1_BASIC
    )
    flagged_sections = models.JSONField(
        default=list,
        blank=True,
        help_text="List of onboarding stages flagged by admin (e.g. ['STAGE_1', 'STAGE_2'])."
    )
    admin_review_note = models.TextField(
        null=True,
        blank=True,
        help_text="Specific instructions from the admin explaining what the applicant must fix."
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    trust_score = models.IntegerField(
        default=50, 
        help_text="0-100 score. High scores can auto-approve products. Low scores flag for manual review."
    )

    def __str__(self):
        return f"{self.business_name} - {self.get_verification_status_display()}"


class VendorWallet(models.Model):
    provider = models.OneToOneField(ProviderProfile, on_delete=models.CASCADE, related_name='wallet')
    pending_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
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
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
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
        unique_together = ('user', 'provider')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} follows {self.provider.business_name}"