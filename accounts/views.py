import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Avg, Count

from .forms import CustomerSignUpForm, UserUpdateForm
from .models import ProviderProfile, VendorWallet
from orders.models import ShippingAddress
from feedback.models import Feedback


def _safe_redirect(namespaced_url, fallback_url):
    """Safely resolves either namespaced ('accounts:provider_status') or un-namespaced URLs."""
    try:
        return redirect(namespaced_url)
    except NoReverseMatch:
        return redirect(fallback_url)


@login_required(login_url='/accounts/login/')
def profile_view(request):
    user = request.user
    has_provider = hasattr(user, 'provider_profile')
    provider = user.provider_profile if has_provider else None
    kyc_locked = bool(provider and provider.verification_status in ['APPROVED', 'ACTIVE'])

    form = UserUpdateForm(instance=user)
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action', 'update_profile')

        # 1. Personal Profile Update (Protects KYC-verified legal names)
        if action == 'update_profile':
            locked_first = user.first_name
            locked_last = user.last_name
            form = UserUpdateForm(request.POST, instance=user)
            if form.is_valid():
                updated_user = form.save(commit=False)
                if kyc_locked:
                    updated_user.first_name = locked_first
                    updated_user.last_name = locked_last
                updated_user.save()
                messages.success(request, "Your account details have been updated.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the highlighted errors below.")

        # 2. Password Change (Keeps session active)
        elif action == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                saved_user = password_form.save()
                update_session_auth_hash(request, saved_user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect('accounts:profile')
            else:
                for field, errors in password_form.errors.items():
                    for err in errors:
                        messages.error(request, err)

        # 3. Add Saved Delivery Address
        elif action == 'add_address':
            label = request.POST.get('label', 'Home').strip() or 'Home'
            first_name = request.POST.get('first_name', '').strip() or user.first_name or user.username
            last_name = request.POST.get('last_name', '').strip() or user.last_name
            phone = request.POST.get('phone', '').strip()
            alt_phone = request.POST.get('alt_phone', '').strip()
            whatsapp = request.POST.get('whatsapp', '').strip()
            region = request.POST.get('region', '').strip()
            city = request.POST.get('city', '').strip()
            street_address = request.POST.get('street_address', '').strip()
            landmark = request.POST.get('landmark', '').strip()
            make_default = request.POST.get('is_default') == 'on'

            if not (phone and region and street_address):
                messages.error(request, "Please provide a phone number, state/region, and street address.")
            else:
                with transaction.atomic():
                    is_first = not user.addresses.exists()
                    if make_default or is_first:
                        user.addresses.update(is_default=False)
                    ShippingAddress.objects.create(
                        user=user,
                        label=label,
                        first_name=first_name,
                        last_name=last_name,
                        phone=phone,
                        alt_phone=alt_phone,
                        whatsapp=whatsapp,
                        region=region,
                        city=city,
                        street_address=street_address,
                        landmark=landmark,
                        is_default=(make_default or is_first)
                    )
                messages.success(request, f"Delivery address '{label}' saved to your address book.")
            return redirect('accounts:profile')

        # 4. Set Default Delivery Address
        elif action == 'set_default_address':
            addr_id = request.POST.get('address_id')
            addr = get_object_or_404(ShippingAddress, id=addr_id, user=user)
            with transaction.atomic():
                user.addresses.update(is_default=False)
                addr.is_default = True
                addr.save(update_fields=['is_default'])
            messages.success(request, f"'{addr.label}' is now your default checkout address.")
            return redirect('accounts:profile')

        # 5. Delete Delivery Address
        elif action == 'delete_address':
            addr_id = request.POST.get('address_id')
            addr = get_object_or_404(ShippingAddress, id=addr_id, user=user)
            was_default = addr.is_default
            addr.delete()
            if was_default:
                next_addr = user.addresses.order_by('-created_at').first()
                if next_addr:
                    next_addr.is_default = True
                    next_addr.save(update_fields=['is_default'])
            messages.info(request, "Delivery address removed.")
            return redirect('accounts:profile')

    avg_rating = 0
    review_count = 0
    star_percentage = "0%"
    recent_reviews = []

    if has_provider:
        stats = Feedback.objects.filter(
            target_provider=user,
            is_verified=True
        ).aggregate(
            average_score=Avg('overall_rating'),
            total_reviews=Count('id')
        )

        avg_rating = stats['average_score'] or 0
        review_count = stats['total_reviews']
        star_percentage = f"{(avg_rating / 5) * 100}%"

        recent_reviews = Feedback.objects.filter(
            target_provider=user,
            is_verified=True
        ).select_related('customer').order_by('-created_at')[:10]

    context = {
        'form': form,
        'password_form': password_form,
        'kyc_locked': kyc_locked,
        'saved_addresses': user.addresses.all().order_by('-is_default', '-created_at'),
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'star_percentage': star_percentage,
        'recent_reviews': recent_reviews,
    }

    return render(request, 'accounts/profile.html', context)


def register_customer(request):
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.role = 'CUSTOMER'
                user.save()

                login(request, user)
                return redirect('marketplace:home')

            except IntegrityError:
                messages.error(request, "That username is already taken. Please choose another.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = CustomerSignUpForm()

    return render(request, 'accounts/register.html', {'form': form})


def custom_logout(request):
    logout(request)
    return redirect('marketplace:home')


@login_required
def apply_provider(request):
    if hasattr(request.user, 'provider_profile'):
        return _safe_redirect('accounts:provider_status', 'provider_status')

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.save()

        ProviderProfile.objects.create(
            user=request.user,
            phone=request.POST.get('phone'),
            dob=request.POST.get('dob'),
            residential_address=request.POST.get('residential_address'),
            business_name=request.POST.get('business_name'),
            provider_type=request.POST.get('provider_type'),
            business_category=request.POST.get('business_category'),
        )
        return _safe_redirect('accounts:provider_status', 'provider_status')

    return render(request, 'dashboard/provider_application.html')


@login_required
def provider_status(request):
    if not hasattr(request.user, 'provider_profile'):
        return _safe_redirect('accounts:apply_provider', 'apply_provider')

    profile = request.user.provider_profile

    if profile.verification_status == 'ACTIVE':
        return redirect('dashboard:provider_dashboard')

    if request.method == 'POST':
        if profile.verification_status == 'STAGE_1_BASIC':
            profile.id_type = request.POST.get('id_type')
            if 'id_document' in request.FILES:
                profile.id_document = request.FILES['id_document']
            if 'selfie_image' in request.FILES:
                profile.selfie_image = request.FILES['selfie_image']

            profile.verification_status = 'STAGE_2_KYC'
            profile.save()
            messages.success(request, "Documents Submitted Successfully.")

        elif profile.verification_status == 'STAGE_2_KYC':
            profile.business_description = request.POST.get('business_description')
            profile.cac_registration_number = request.POST.get('cac_registration_number')
            if 'business_certificate' in request.FILES:
                profile.business_certificate = request.FILES['business_certificate']

            profile.verification_status = 'STAGE_3_BUSINESS'
            profile.save()
            messages.success(request, "Business details recorded.")

        elif profile.verification_status == 'STAGE_3_BUSINESS':
            profile.region = request.POST.get('region')
            profile.store_address = request.POST.get('store_address')
            profile.latitude = request.POST.get('latitude') or None
            profile.longitude = request.POST.get('longitude') or None

            if 'exterior_image' in request.FILES:
                profile.exterior_image = request.FILES['exterior_image']
            if 'interior_image' in request.FILES:
                profile.interior_image = request.FILES['interior_image']
            if 'signboard_image' in request.FILES:
                profile.signboard_image = request.FILES['signboard_image']

            profile.verification_status = 'STAGE_4_LOCATION'
            profile.save()
            messages.success(request, "Location pinned! Your application is now under admin review.")

        elif profile.verification_status == 'APPROVED':
            bank_code = request.POST.get('bank_code')
            bank_name = request.POST.get('bank_name')
            account_number = request.POST.get('account_number')

            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            verify_url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"

            try:
                response = requests.get(verify_url, headers=headers, timeout=10)
                res_data = response.json()

                if res_data.get('status'):
                    resolved_name = res_data['data']['account_name']

                    account_name_clean = resolved_name.strip().lower()
                    personal_first = request.user.first_name.strip().lower()
                    personal_last = request.user.last_name.strip().lower()
                    business_clean = profile.business_name.strip().lower()

                    has_personal_name = (personal_first and personal_last and personal_first in account_name_clean and personal_last in account_name_clean)
                    has_business_name = (business_clean and business_clean in account_name_clean)

                    if not (has_personal_name or has_business_name):
                        messages.error(
                            request,
                            f"Bank Rejection: The account name returned by your bank is '{resolved_name}'. This does not match your registered identity or business name."
                        )
                        return _safe_redirect('accounts:provider_status', 'provider_status')

                    profile.bank_name = bank_name
                    profile.account_number = account_number
                    profile.account_name = resolved_name

                    profile.verification_status = 'ACTIVE'
                    profile.save()
                    VendorWallet.objects.get_or_create(provider=profile)

                    messages.success(request, f"Bank verified successfully as {resolved_name}! Welcome to All Things.")
                    return redirect('dashboard:provider_dashboard')
                else:
                    messages.error(request, "Invalid account number or bank selected. Please check and try again.")
                    return _safe_redirect('accounts:provider_status', 'provider_status')

            except Exception:
                messages.error(request, "Could not reach the banking network at this time. Please try again later.")
                return _safe_redirect('accounts:provider_status', 'provider_status')

        return _safe_redirect('accounts:provider_status', 'provider_status')

    context = {'profile': profile}
    if profile.verification_status == 'APPROVED':
        try:
            headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
            banks_response = requests.get("https://api.paystack.co/bank?currency=NGN", headers=headers, timeout=8)
            if banks_response.status_code == 200:
                context['banks'] = banks_response.json().get('data', [])
        except requests.exceptions.RequestException:
            context['banks'] = []

    return render(request, 'dashboard/provider_status.html', context)