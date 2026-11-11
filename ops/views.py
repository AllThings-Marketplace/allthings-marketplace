from decimal import Decimal
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import ProviderProfile, VendorWallet, VendorTransaction
from marketplace.models import Product, Service
from orders.models import SupportTicket, PaymentAttempt
from orders.tasks import trigger_escrow_auto_clear_if_due


def _notify_user(recipient, title, message, target_obj=None, notif_type='SYSTEM'):
    """
    Sends an in-app Bell Notification (and triggers the HTML email signal)
    whenever an administrator approves/flags KYC or moderates a listing.
    """
    if not recipient:
        return
    try:
        from notifications.models import Notification
        ct = ContentType.objects.get_for_model(target_obj) if target_obj else None
        obj_id = target_obj.id if target_obj else None
        Notification.objects.create(
            recipient=recipient,
            notification_type=notif_type,
            title=title,
            message=message,
            content_type=ct,
            object_id=obj_id,
        )
    except Exception:
        pass


def _record_ops_audit(user, target_obj, action_summary):
    """
    Records an immutable staff audit log entry in Django's built-in LogEntry
    table (requires zero schema migrations and is visible in both Ops & Django Admin).
    """
    try:
        ct = ContentType.objects.get_for_model(target_obj)
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ct.pk,
            object_id=target_obj.pk,
            object_repr=str(target_obj)[:200],
            action_flag=CHANGE,
            change_message=action_summary,
        )
    except Exception:
        pass


def _get_ops_nav_counts():
    """Shared badge counters for the top Operations navigation bar."""
    pending_kyc = ProviderProfile.objects.filter(verification_status='STAGE_4_LOCATION').count()
    pending_products = Product.objects.filter(status='PENDING').count()
    pending_services = Service.objects.filter(status='PENDING').count()
    active_disputes = SupportTicket.objects.filter(status__in=['OPEN', 'IN_PROGRESS']).count()
    return {
        'nav_pending_kyc': pending_kyc,
        'nav_pending_listings': pending_products + pending_services,
        'nav_active_disputes': active_disputes,
    }


@staff_member_required
def ops_overview(request):
    """Main Operations Command Center overview with platform health, escrow, and audit previews."""
    trigger_escrow_auto_clear_if_due()
    nav_counts = _get_ops_nav_counts()

    active_providers_count = ProviderProfile.objects.filter(verification_status='ACTIVE').count()
    flagged_kyc_count = ProviderProfile.objects.filter(verification_status='FLAGGED').count()
    unverified_payments_count = PaymentAttempt.objects.filter(
        order__status='unpaid'
    ).exclude(status='successful').count()

    wallet_totals = VendorWallet.objects.aggregate(
        total_escrow_locked=Sum('pending_balance'),
        total_available=Sum('available_balance'),
        total_paid_out=Sum('total_withdrawn'),
    )

    platform_commission_total = VendorTransaction.objects.exclude(
        status__in=['FAILED', 'CANCELLED', 'REFUNDED']
    ).aggregate(total_comm=Sum('commission'))['total_comm'] or Decimal('0.00')

    recent_kyc_queue = ProviderProfile.objects.filter(
        verification_status='STAGE_4_LOCATION'
    ).select_related('user').order_by('-applied_at', '-id')[:5]

    recent_disputes = SupportTicket.objects.filter(
        status__in=['OPEN', 'IN_PROGRESS']
    ).select_related('user').order_by('-created_at')[:5]

    recent_audit_logs = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:6]

    context = {
        **nav_counts,
        'pending_kyc_count': nav_counts['nav_pending_kyc'],
        'pending_listings_count': nav_counts['nav_pending_listings'],
        'active_disputes_count': nav_counts['nav_active_disputes'],
        'active_providers_count': active_providers_count,
        'flagged_kyc_count': flagged_kyc_count,
        'unverified_payments_count': unverified_payments_count,
        'total_escrow_locked': wallet_totals['total_escrow_locked'] or Decimal('0.00'),
        'total_available': wallet_totals['total_available'] or Decimal('0.00'),
        'total_paid_out': wallet_totals['total_paid_out'] or Decimal('0.00'),
        'platform_commission_total': platform_commission_total,
        'recent_kyc_queue': recent_kyc_queue,
        'recent_disputes': recent_disputes,
        'recent_audit_logs': recent_audit_logs,
    }
    return render(request, 'ops/overview.html', context)


@staff_member_required
def kyc_moderation_list(request):
    """Lists provider KYC dossiers with status filtering (Pending Review, Flagged, Approved, Active)."""
    status_filter = request.GET.get('status', 'STAGE_4_LOCATION').upper().strip()
    valid_statuses = ['STAGE_4_LOCATION', 'FLAGGED', 'APPROVED', 'ACTIVE', 'ALL']
    if status_filter not in valid_statuses:
        status_filter = 'STAGE_4_LOCATION'

    qs = ProviderProfile.objects.select_related('user').order_by('-applied_at', '-id')
    if status_filter != 'ALL':
        qs = qs.filter(verification_status=status_filter)

    context = {
        **_get_ops_nav_counts(),
        'dossiers': qs,
        'status_filter': status_filter,
    }
    return render(request, 'ops/kyc_list.html', context)


@staff_member_required
def kyc_dossier_detail(request, profile_id):
    """
    Side-by-side KYC Dossier Inspection & Action Hub.
    Allows staff to Approve (-> APPROVED or ACTIVE if bank is already linked)
    or Flag specific stages (-> FLAGGED) and dispatches an immediate notification.
    """
    profile = get_object_or_404(ProviderProfile.objects.select_related('user'), id=profile_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_note = request.POST.get('admin_note', '').strip()
        now = timezone.now()

        with transaction.atomic():
            if action == 'approve':
                has_verified_bank = bool(profile.account_number and profile.bank_code and profile.account_name)
                target_status = 'ACTIVE' if has_verified_bank else 'APPROVED'

                profile.verification_status = target_status
                profile.flagged_sections = []
                profile.admin_review_note = ''
                profile.reviewed_at = now
                if not profile.approved_at:
                    profile.approved_at = now
                profile.save(update_fields=[
                    'verification_status',
                    'flagged_sections',
                    'admin_review_note',
                    'reviewed_at',
                    'approved_at',
                ])

                _record_ops_audit(
                    request.user,
                    profile,
                    f"KYC Dossier approved (-> {target_status}) for {profile.business_name}."
                )

                if target_status == 'ACTIVE':
                    _notify_user(
                        recipient=profile.user,
                        title=f"Store Activated: {profile.business_name}!",
                        message="Your KYC dossier has been approved and your storefront is now fully active on AllThings!",
                        target_obj=profile,
                        notif_type='SYSTEM',
                    )
                    messages.success(request, f"Dossier for {profile.business_name} approved and store set to ACTIVE!")
                else:
                    _notify_user(
                        recipient=profile.user,
                        title=f"KYC Approved for {profile.business_name}!",
                        message="Congratulations! Your KYC dossier has been approved. Complete Stage 5 (Settlement Bank Verification) to activate your storefront.",
                        target_obj=profile,
                        notif_type='SYSTEM',
                    )
                    messages.success(request, f"Dossier for {profile.business_name} approved! Vendor has been notified to link their payout bank.")

            elif action == 'flag':
                flagged_sections = request.POST.getlist('flagged_sections')
                if not flagged_sections:
                    messages.error(request, "Please select at least one section (Stage 1–4) to flag for correction.")
                    return redirect('ops:kyc_detail', profile_id=profile.id)

                if not admin_note:
                    messages.error(request, "Please provide a clear compliance note explaining what the applicant needs to fix.")
                    return redirect('ops:kyc_detail', profile_id=profile.id)

                profile.verification_status = 'FLAGGED'
                profile.flagged_sections = flagged_sections
                profile.admin_review_note = admin_note
                profile.reviewed_at = now
                profile.save(update_fields=[
                    'verification_status',
                    'flagged_sections',
                    'admin_review_note',
                    'reviewed_at',
                ])

                _record_ops_audit(
                    request.user,
                    profile,
                    f"KYC Dossier flagged ({', '.join(flagged_sections)}): {admin_note[:100]}"
                )

                _notify_user(
                    recipient=profile.user,
                    title=f"Action Required: Update Your KYC Dossier ({profile.business_name})",
                    message=f"Our compliance team requested a quick update on your application: \"{admin_note}\"",
                    target_obj=profile,
                    notif_type='SYSTEM',
                )
                messages.warning(request, f"Dossier for {profile.business_name} flagged for corrections and vendor notified.")

        return redirect('ops:kyc_list')

    context = {
        **_get_ops_nav_counts(),
        'profile': profile,
    }
    return render(request, 'ops/kyc_detail.html', context)


@staff_member_required
def listing_moderation_list(request):
    """Lists products and services with status filtering (PENDING, APPROVED, REJECTED)."""
    status_filter = request.GET.get('status', 'PENDING').upper().strip()
    if status_filter not in ['PENDING', 'APPROVED', 'REJECTED']:
        status_filter = 'PENDING'

    products_qs = Product.objects.filter(
        status=status_filter
    ).select_related('provider__user', 'category').prefetch_related('images').order_by('-id')[:50]

    services_qs = Service.objects.filter(
        status=status_filter
    ).select_related('provider__user', 'category').prefetch_related('packages').order_by('-id')[:50]

    context = {
        **_get_ops_nav_counts(),
        'pending_products': products_qs,
        'pending_services': services_qs,
        'status_filter': status_filter,
    }
    return render(request, 'ops/listing_list.html', context)


@staff_member_required
@transaction.atomic
def moderate_listing_action(request, item_type, item_id):
    """Approves or rejects a product or service listing, syncs image status, and notifies the provider."""
    if request.method != 'POST':
        return redirect('ops:listing_list')

    action = request.POST.get('action')
    moderation_note = request.POST.get('moderation_note', '').strip()

    if item_type == 'product':
        item = get_object_or_404(Product.objects.select_related('provider__user'), id=item_id)
    elif item_type == 'service':
        item = get_object_or_404(Service.objects.select_related('provider__user'), id=item_id)
    else:
        return redirect('ops:listing_list')

    provider_user = item.provider.user if item.provider else None

    if action == 'approve':
        item.status = 'APPROVED'
        item.is_active = True
        item.moderation_note = ''
        item.save(update_fields=['status', 'is_active', 'moderation_note'])

        # Ensure all non-rejected product images are marked APPROVED so they display immediately
        if item_type == 'product':
            item.images.exclude(processing_status='REJECTED').update(processing_status='APPROVED')

        _record_ops_audit(request.user, item, f"Approved {item_type} listing '{item.name}'.")

        _notify_user(
            recipient=provider_user,
            title=f"Listing Approved: {item.name}",
            message=f"Your {item_type} '{item.name}' has been approved and is now live on the AllThings Marketplace!",
            target_obj=item,
            notif_type='SYSTEM',
        )
        messages.success(request, f"'{item.name}' approved and published live!")

    elif action == 'reject':
        note = moderation_note or 'Listing did not meet AllThings marketplace quality or safety guidelines.'
        item.status = 'REJECTED'
        item.is_active = False
        item.moderation_note = note
        item.save(update_fields=['status', 'is_active', 'moderation_note'])

        _record_ops_audit(request.user, item, f"Rejected {item_type} listing '{item.name}': {note[:100]}")

        _notify_user(
            recipient=provider_user,
            title=f"Listing Needs Update: {item.name}",
            message=f"Your {item_type} '{item.name}' was not approved. Reason: \"{note}\"",
            target_obj=item,
            notif_type='SYSTEM',
        )
        messages.warning(request, f"'{item.name}' rejected and provider notified.")

    return redirect('ops:listing_list')


@staff_member_required
def disputes_arbitration_list(request):
    """Lists support tickets and escrow dispute cases with status filtering."""
    status_filter = request.GET.get('status', 'ACTIVE').upper().strip()

    qs = SupportTicket.objects.select_related(
        'user', 'order', 'order_item__product', 'service_order__service'
    ).order_by('-created_at')

    if status_filter == 'RESOLVED':
        qs = qs.filter(status__in=['RESOLVED_CUSTOMER', 'RESOLVED_PROVIDER', 'CLOSED'])
    elif status_filter == 'ALL':
        pass
    else:
        status_filter = 'ACTIVE'
        qs = qs.filter(status__in=['OPEN', 'IN_PROGRESS'])

    context = {
        **_get_ops_nav_counts(),
        'tickets': qs,
        'status_filter': status_filter,
    }
    return render(request, 'ops/disputes_list.html', context)