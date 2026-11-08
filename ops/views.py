from decimal import Decimal
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import ProviderProfile
from marketplace.models import Product, Service
from orders.models import SupportTicket


@staff_member_required
def ops_overview(request):
    """Main Operations Command Center overview with platform metrics."""
    pending_kyc_count = ProviderProfile.objects.filter(verification_status='STAGE_4_LOCATION').count()
    pending_products_count = Product.objects.filter(status='PENDING').count()
    pending_services_count = Service.objects.filter(status='PENDING').count()
    active_disputes_count = SupportTicket.objects.filter(status__in=['OPEN', 'IN_PROGRESS']).count()

    context = {
        'pending_kyc_count': pending_kyc_count,
        'pending_listings_count': pending_products_count + pending_services_count,
        'active_disputes_count': active_disputes_count,
    }
    return render(request, 'ops/overview.html', context)


@staff_member_required
def kyc_moderation_list(request):
    """Lists all vendor/provider dossiers awaiting compliance review (STAGE_4_LOCATION)."""
    dossiers = ProviderProfile.objects.filter(
        verification_status='STAGE_4_LOCATION'
    ).select_related('user').order_by('-created_at')

    return render(request, 'ops/kyc_list.html', {'dossiers': dossiers})


@staff_member_required
def kyc_dossier_detail(request, profile_id):
    """
    Side-by-side KYC Dossier Inspection & Action Hub.
    Allows staff to Approve (-> APPROVED) or Flag specific stages (-> FLAGGED).
    """
    profile = get_object_or_404(ProviderProfile.objects.select_related('user'), id=profile_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_note = request.POST.get('admin_note', '').strip()

        with transaction.atomic():
            if action == 'approve':
                profile.verification_status = 'APPROVED'
                profile.flagged_sections = []
                profile.admin_review_note = ''
                if not profile.approved_at:
                    profile.approved_at = timezone.now()
                profile.save(update_fields=['verification_status', 'flagged_sections', 'admin_review_note', 'approved_at'])

                messages.success(request, f"Dossier for {profile.business_name} approved! Vendor can now link their payout bank.")

            elif action == 'flag':
                flagged_sections = request.POST.getlist('flagged_sections')
                if not flagged_sections:
                    messages.error(request, "Please select at least one section to flag for correction.")
                    return redirect('ops:kyc_detail', profile_id=profile.id)

                if not admin_note:
                    messages.error(request, "Please provide an explanation note for the vendor.")
                    return redirect('ops:kyc_detail', profile_id=profile.id)

                profile.verification_status = 'FLAGGED'
                profile.flagged_sections = flagged_sections
                profile.admin_review_note = admin_note
                profile.save(update_fields=['verification_status', 'flagged_sections', 'admin_review_note'])

                messages.warning(request, f"Dossier for {profile.business_name} flagged for corrections.")

        return redirect('ops:kyc_list')

    return render(request, 'ops/kyc_detail.html', {'profile': profile})


@staff_member_required
def listing_moderation_list(request):
    """Lists pending products and services awaiting moderation."""
    pending_products = Product.objects.filter(status='PENDING').select_related('provider', 'category')
    pending_services = Service.objects.filter(status='PENDING').select_related('provider', 'category')

    context = {
        'pending_products': pending_products,
        'pending_services': pending_services,
    }
    return render(request, 'ops/listing_list.html', context)


@staff_member_required
@transaction.atomic
def moderate_listing_action(request, item_type, item_id):
    """Approves or rejects a product or service listing."""
    if request.method != 'POST':
        return redirect('ops:listing_list')

    action = request.POST.get('action')
    moderation_note = request.POST.get('moderation_note', '').strip()

    if item_type == 'product':
        item = get_object_or_404(Product, id=item_id)
    elif item_type == 'service':
        item = get_object_or_404(Service, id=item_id)
    else:
        return redirect('ops:listing_list')

    if action == 'approve':
        item.status = 'APPROVED'
        item.is_active = True
        item.moderation_note = ''
        item.save(update_fields=['status', 'is_active', 'moderation_note'])
        messages.success(request, f"'{item.name}' approved and published live!")
    elif action == 'reject':
        item.status = 'REJECTED'
        item.is_active = False
        item.moderation_note = moderation_note or 'Listing did not meet platform guidelines.'
        item.save(update_fields=['status', 'is_active', 'moderation_note'])
        messages.warning(request, f"'{item.name}' rejected.")

    return redirect('ops:listing_list')


@staff_member_required
def disputes_arbitration_list(request):
    """Lists all open support tickets and escrow dispute cases."""
    tickets = SupportTicket.objects.filter(
        status__in=['OPEN', 'IN_PROGRESS']
    ).select_related('user', 'order', 'service_order').order_by('-created_at')

    return render(request, 'ops/disputes_list.html', {'tickets': tickets})