import re
import logging
import secrets
import datetime
import threading
import requests
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import NoReverseMatch
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.db.models import Avg, Count
from django.core.exceptions import ValidationError

from marketplace.validators import validate_product_image, validate_kyc_document
from .forms import CustomerSignUpForm, UserUpdateForm
from .models import ProviderProfile, VendorWallet, ContactOTP
from orders.models import ShippingAddress
from feedback.models import Feedback

logger = logging.getLogger(__name__)

NG_PHONE_VALIDATOR = re.compile(r'^(?:\+?234|0)[789][01]\d{8}$')


def _safe_redirect(namespaced_url, fallback_url):
    """Safely resolves either namespaced ('accounts:provider_status') or un-namespaced URLs."""
    try:
        return redirect(namespaced_url)
    except NoReverseMatch:
        return redirect(fallback_url)


def _normalize_ng_phone(raw_phone):
    """Normalizes Nigerian phone numbers (e.g. 08031234567 -> +2348031234567)."""
    cleaned = re.sub(r'[\s\-().]', '', str(raw_phone or '').strip())
    if cleaned.startswith('0') and len(cleaned) == 11:
        return '+234' + cleaned[1:]
    if cleaned.startswith('234') and len(cleaned) == 13:
        return '+' + cleaned
    return cleaned


def _parse_from_email(raw_from):
    """Extracts ('Sender Name', 'email@domain.com') from DEFAULT_FROM_EMAIL."""
    raw = (raw_from or 'AllThings Marketplace <noreply@allthings.com>').strip()
    match = re.match(r'^(.*?)\s*<([^>]+)>$', raw)
    if match:
        name = match.group(1).strip().strip('"') or "AllThings Marketplace"
        email = match.group(2).strip()
        return name, email
    return "AllThings Marketplace", raw


def _send_email_otp(recipient_email, recipient_name, code):
    """
    Sends Email OTP using:
    1. Brevo HTTPS API (Port 443 - never blocked by Railway firewalls) if BREVO_API_KEY is set.
    2. Standard Django SMTP with a strict 8-second timeout so Gunicorn workers never hang.
    Returns (sent_ok: bool, info: str).
    """
    subject = f"{code} is your AllThings Verification Code"
    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your 6-digit verification code for your AllThings account is:\n\n"
        f"    {code}\n\n"
        f"This code expires in 10 minutes. Never share this code with anyone."
    )
    html_body = (
        f"<div style='font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;"
        f"border:1px solid #e2e8f0;border-radius:12px;'>"
        f"<h2 style='color:#0f172a;margin-top:0;'>AllThings Verification Code</h2>"
        f"<p style='color:#475569;font-size:15px;'>Hi <strong>{recipient_name}</strong>,</p>"
        f"<p style='color:#475569;font-size:15px;'>Use the 6-digit code below to verify your email address:</p>"
        f"<div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;"
        f"text-align:center;font-size:28px;font-weight:800;letter-spacing:6px;color:#1d4ed8;margin:20px 0;'>"
        f"{code}</div>"
        f"<p style='color:#64748b;font-size:13px;'>This code expires in 10 minutes. If you did not request this code, please ignore this email.</p>"
        f"</div>"
    )

    sender_name, sender_email = _parse_from_email(
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'AllThings Marketplace <noreply@allthings.com>')
    )

    # 1. Try Brevo HTTP API first (Port 443 - bypasses Railway SMTP port blocks)
    brevo_api_key = getattr(settings, 'BREVO_API_KEY', '').strip()
    if not brevo_api_key:
        # Also auto-detect if user pasted a Brevo 'xkeysib-...' API key into EMAIL_HOST_PASSWORD
        smtp_pass = getattr(settings, 'EMAIL_HOST_PASSWORD', '').strip()
        if smtp_pass.startswith('xkeysib-'):
            brevo_api_key = smtp_pass

    if brevo_api_key:
        try:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "api-key": brevo_api_key,
                    "content-type": "application/json",
                },
                json={
                    "sender": {"name": sender_name, "email": sender_email},
                    "to": [{"email": recipient_email, "name": recipient_name}],
                    "subject": subject,
                    "textContent": text_body,
                    "htmlContent": html_body,
                },
                timeout=8,
            )
            if resp.status_code in (200, 201, 202):
                logger.info("Brevo HTTP API sent OTP email to %s", recipient_email)
                return True, "Sent via Brevo HTTP API"
            logger.warning("Brevo HTTP API error (%s): %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("Brevo HTTP API exception: %s", exc)

    # 2. Fallback to Django SMTP with strict 8-second timeout (prevents Gunicorn worker hang)
    if not getattr(settings, 'EMAIL_HOST_USER', ''):
        logger.warning("EMAIL_HOST_USER / BREVO_API_KEY not configured. OTP for %s is %s", recipient_email, code)
        return False, "Email credentials not configured."

    try:
        connection = get_connection(timeout=8, fail_silently=False)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=f"{sender_name} <{sender_email}>",
            to=[recipient_email],
            connection=connection,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("SMTP sent OTP email to %s", recipient_email)
        return True, "Sent via SMTP"
    except Exception as exc:
        logger.error("SMTP OTP delivery failed for %s: %s", recipient_email, exc)
        return False, str(exc)


def _send_sms_otp(phone_e164, code):
    """
    Sends SMS OTP via Termii (if TERMII_API_KEY is configured in settings/.env).
    Automatically attempts the configured channel (defaults to 'dnd' then 'generic')
    and logs the exact gateway response for debugging on Railway.
    """
    api_key = getattr(settings, 'TERMII_API_KEY', '').strip()
    sender_id = getattr(settings, 'TERMII_SENDER_ID', 'AllThings').strip()
    preferred_channel = getattr(settings, 'TERMII_CHANNEL', 'generic').strip().lower()
    base_url = getattr(settings, 'TERMII_BASE_URL', 'https://v3.api.termii.com').rstrip('/')

    if not api_key:
        logger.warning("TERMII_API_KEY not set. SMS OTP for %s is %s", phone_e164, code)
        return False, "SMS gateway key not configured."

    clean_phone = phone_e164.lstrip('+')
    sms_text = f"Your AllThings verification code is {code}. Valid for 10 minutes. Do not share this code."

    # Try preferred channel first, then fallback channel if rejected
    channels_to_try = [preferred_channel]
    if preferred_channel != 'generic':
        channels_to_try.append('generic')
    elif preferred_channel != 'dnd':
        channels_to_try.append('dnd')

    last_error = "Unknown SMS gateway error"
    for channel in channels_to_try:
        try:
            payload = {
                "to": clean_phone,
                "from": sender_id if channel != 'dnd' else getattr(settings, 'TERMII_DND_SENDER_ID', 'N-Alert'),
                "sms": sms_text,
                "type": "plain",
                "channel": channel,
                "api_key": api_key,
            }
            resp = requests.post(f"{base_url}/api/sms/send", json=payload, timeout=8)
            if resp.status_code in (200, 201):
                logger.info("Termii SMS OTP sent to %s via '%s' channel", clean_phone, channel)
                return True, "Sent via SMS"
            last_error = f"HTTP {resp.status_code}: {resp.text}"
            logger.warning("Termii SMS failed on channel '%s' for %s -> %s", channel, clean_phone, last_error)
        except Exception as exc:
            last_error = str(exc)
            logger.error("Termii SMS exception on channel '%s' for %s: %s", channel, clean_phone, exc)

    return False, last_error


def sell_on_allthings(request):
    """
    Dedicated 'Sell on AllThings' landing page explaining how vendor sales,
    service bookings, escrow protection, and instant payouts work.
    """
    return render(request, 'accounts/sell_on_allthings.html')


@login_required
@require_POST
def send_verification_otp(request):
    """
    AJAX endpoint that generates and dispatches a 6-digit OTP to either
    the user's Email Address or Primary Phone Number with a 60-second cooldown.
    """
    channel = request.POST.get('channel', '').upper().strip()
    raw_target = request.POST.get('target', '').strip()

    if channel not in ['EMAIL', 'PHONE']:
        return JsonResponse({'status': 'error', 'message': 'Invalid verification channel.'}, status=400)

    if channel == 'EMAIL':
        target = (raw_target or request.user.email).strip().lower()
        if not target or '@' not in target:
            return JsonResponse({'status': 'error', 'message': 'Please enter a valid email address.'}, status=400)
    else:
        cleaned_digits = re.sub(r'[\s\-().]', '', raw_target)
        if not NG_PHONE_VALIDATOR.match(cleaned_digits):
            return JsonResponse({
                'status': 'error',
                'message': 'Please enter a valid 11-digit Nigerian phone number (e.g. 08031234567).'
            }, status=400)
        target = _normalize_ng_phone(cleaned_digits)

    # 1. Enforce 60-Second Rate-Limit Cooldown
    recent_otp = ContactOTP.objects.filter(
        user=request.user,
        channel=channel,
        target=target
    ).first()

    if recent_otp and not recent_otp.is_verified:
        elapsed = (timezone.now() - recent_otp.created_at).total_seconds()
        if elapsed < 55:
            wait_secs = int(60 - elapsed)
            return JsonResponse({
                'status': 'error',
                'message': f'Please wait {wait_secs}s before requesting another code.'
            }, status=429)

    # 2. Generate Cryptographically Random 6-Digit Code
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = timezone.now() + datetime.timedelta(minutes=10)

    ContactOTP.objects.filter(
        user=request.user,
        channel=channel,
        is_verified=False
    ).delete()

    ContactOTP.objects.create(
        user=request.user,
        channel=channel,
        target=target,
        code=code,
        expires_at=expires_at
    )

    # 3. Dispatch via Email or SMS (with strict timeouts so Gunicorn never hangs)
    show_fallback = settings.DEBUG or getattr(settings, 'SHOW_OTP_FALLBACK', False)
    dev_code_hint = None
    recipient_name = request.user.first_name or request.user.username

    if channel == 'EMAIL':
        sent_ok, info = _send_email_otp(target, recipient_name, code)
        if sent_ok:
            delivery_msg = f"A 6-digit verification code has been sent to {target}."
        else:
            delivery_msg = f"Verification code generated for {target}."
            if show_fallback:
                dev_code_hint = code
    else:
        sent_ok, info = _send_sms_otp(target, code)
        if sent_ok:
            delivery_msg = f"A 6-digit SMS code has been sent to {target}."
        else:
            delivery_msg = f"SMS verification code generated for {target}."
            if show_fallback:
                dev_code_hint = code

    if show_fallback and not dev_code_hint:
        dev_code_hint = code

    response_payload = {
        'status': 'success',
        'message': delivery_msg,
        'target': target,
        'cooldown': 60,
    }
    if dev_code_hint:
        response_payload['dev_code'] = dev_code_hint

    return JsonResponse(response_payload)


@login_required
@require_POST
def verify_contact_otp(request):
    """
    AJAX endpoint that verifies a 6-digit OTP against the most recent active
    ContactOTP record, enforcing a 5-attempt brute-force lockout and 10-minute expiry.
    """
    channel = request.POST.get('channel', '').upper().strip()
    raw_target = request.POST.get('target', '').strip()
    submitted_code = request.POST.get('code', '').strip()

    if not submitted_code or len(submitted_code) != 6 or not submitted_code.isdigit():
        return JsonResponse({'status': 'error', 'message': 'Please enter a valid 6-digit code.'}, status=400)

    target = raw_target.lower() if channel == 'EMAIL' else _normalize_ng_phone(raw_target)

    otp_record = ContactOTP.objects.filter(
        user=request.user,
        channel=channel,
        target=target
    ).first()

    if not otp_record:
        return JsonResponse({
            'status': 'error',
            'message': 'No active verification code found. Please click Send Code first.'
        }, status=400)

    if otp_record.is_verified:
        return JsonResponse({'status': 'success', 'message': 'Already verified!', 'target': target})

    if otp_record.is_expired:
        return JsonResponse({
            'status': 'error',
            'message': 'This code has expired. Please request a new code.'
        }, status=400)

    if otp_record.attempts >= 5:
        return JsonResponse({
            'status': 'error',
            'message': 'Too many incorrect attempts. Please request a new code.'
        }, status=429)

    if otp_record.code != submitted_code:
        otp_record.attempts += 1
        otp_record.save(update_fields=['attempts'])
        remaining = max(0, 5 - otp_record.attempts)
        return JsonResponse({
            'status': 'error',
            'message': f'Incorrect code. You have {remaining} attempt(s) remaining.'
        }, status=400)

    otp_record.is_verified = True
    otp_record.verified_at = timezone.now()
    otp_record.save(update_fields=['is_verified', 'verified_at'])

    if channel == 'PHONE':
        request.user.phone_number = raw_target
        request.user.save(update_fields=['phone_number'])

    return JsonResponse({
        'status': 'success',
        'message': f'{otp_record.get_channel_display()} verified successfully!',
        'target': target,
    })


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
    next_url = request.GET.get('next') or request.POST.get('next')
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.role = 'CUSTOMER'
                user.save()

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect('marketplace:home')

            except IntegrityError:
                messages.error(request, "That username is already taken. Please choose another.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = CustomerSignUpForm()

    return render(request, 'accounts/register.html', {'form': form, 'next': next_url})


def custom_logout(request):
    logout(request)
    return redirect('marketplace:home')


@login_required
def apply_provider(request):
    if hasattr(request.user, 'provider_profile'):
        return _safe_redirect('accounts:provider_status', 'provider_status')

    user_email = (request.user.email or '').strip().lower()
    email_already_verified = ContactOTP.objects.filter(
        user=request.user,
        channel='EMAIL',
        target=user_email,
        is_verified=True
    ).exists() if user_email else False

    verified_phone_otp = ContactOTP.objects.filter(
        user=request.user,
        channel='PHONE',
        is_verified=True
    ).first()

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        submitted_email = (request.POST.get('email') or request.user.email or '').strip().lower()
        raw_phone = request.POST.get('phone', '').strip()
        normalized_phone = _normalize_ng_phone(raw_phone)

        # Server-Side Enforcement of Both Email & Phone OTP Verification
        is_email_ok = ContactOTP.objects.filter(
            user=request.user,
            channel='EMAIL',
            target=submitted_email,
            is_verified=True
        ).exists()

        is_phone_ok = ContactOTP.objects.filter(
            user=request.user,
            channel='PHONE',
            target=normalized_phone,
            is_verified=True
        ).exists()

        if not is_email_ok:
            messages.error(request, "Please verify your email address using the 6-digit OTP code before continuing.")
            return render(request, 'dashboard/provider_application.html', {
                'email_already_verified': email_already_verified,
                'verified_phone': verified_phone_otp.target if verified_phone_otp else '',
            })

        if not is_phone_ok:
            messages.error(request, "Please verify your primary phone number via OTP before continuing.")
            return render(request, 'dashboard/provider_application.html', {
                'email_already_verified': is_email_ok,
                'verified_phone': '',
            })

        with transaction.atomic():
            request.user.first_name = first_name
            request.user.last_name = last_name
            if submitted_email and submitted_email != request.user.email:
                request.user.email = submitted_email
            request.user.phone_number = raw_phone
            request.user.save()

            ProviderProfile.objects.create(
                user=request.user,
                phone=raw_phone,
                email_verified=True,
                phone_verified=True,
                dob=request.POST.get('dob'),
                residential_address=request.POST.get('residential_address'),
                business_name=request.POST.get('business_name'),
                provider_type=request.POST.get('provider_type'),
                business_category=request.POST.get('business_category'),
            )

        messages.success(request, "Stage 1 complete! Both your email and phone number are verified.")
        return _safe_redirect('accounts:provider_status', 'provider_status')

    context = {
        'email_already_verified': email_already_verified,
        'verified_phone': verified_phone_otp.target if verified_phone_otp else '',
    }
    return render(request, 'dashboard/provider_application.html', context)


@login_required
def provider_status(request):
    if not hasattr(request.user, 'provider_profile'):
        return _safe_redirect('accounts:apply_provider', 'apply_provider')

    profile = request.user.provider_profile

    if profile.verification_status == 'ACTIVE':
        return redirect('dashboard:provider_dashboard')

    if request.method == 'POST':
        try:
            # STAGE 2: Identity Verification (KYC)
            if profile.verification_status == 'STAGE_1_BASIC':
                id_type = request.POST.get('id_type', '').strip()
                id_doc = request.FILES.get('id_document')
                selfie_img = request.FILES.get('selfie_image')

                if not id_type or not id_doc or not selfie_img:
                    raise ValidationError("Please select an ID type and upload both your government ID and a live selfie.")

                validate_kyc_document(id_doc, allow_pdf=True)
                validate_product_image(selfie_img)

                profile.id_type = id_type
                profile.id_document = id_doc
                profile.selfie_image = selfie_img
                profile.verification_status = 'STAGE_2_KYC'
                profile.save()
                messages.success(request, "Identity documents verified and submitted!")

            # STAGE 3: Business Verification
            elif profile.verification_status == 'STAGE_2_KYC':
                business_desc = request.POST.get('business_description', '').strip()
                if not business_desc:
                    raise ValidationError("Please provide a description of your store or technical expertise.")

                cert_file = request.FILES.get('business_certificate')
                if cert_file:
                    validate_kyc_document(cert_file, allow_pdf=True)
                    profile.business_certificate = cert_file

                profile.business_description = business_desc
                profile.cac_registration_number = request.POST.get('cac_registration_number', '').strip()
                profile.verification_status = 'STAGE_3_BUSINESS'
                profile.save()
                messages.success(request, "Business details recorded.")

            # STAGE 4: Physical Store / Base Location Pinning
            elif profile.verification_status == 'STAGE_3_BUSINESS':
                ext_img = request.FILES.get('exterior_image')
                int_img = request.FILES.get('interior_image')
                sign_img = request.FILES.get('signboard_image')

                if not ext_img or not int_img:
                    raise ValidationError("Please upload both exterior and interior photos of your shop or operating base.")

                validate_product_image(ext_img)
                validate_product_image(int_img)
                if sign_img:
                    validate_product_image(sign_img)
                    profile.signboard_image = sign_img

                profile.region = request.POST.get('region', '').strip()
                profile.store_address = request.POST.get('store_address', '').strip()
                profile.latitude = request.POST.get('latitude') or None
                profile.longitude = request.POST.get('longitude') or None
                profile.exterior_image = ext_img
                profile.interior_image = int_img
                profile.verification_status = 'STAGE_4_LOCATION'
                profile.save()
                messages.success(request, "Location pinned! Your application is now under admin review.")

            # STAGE 5: Paystack Bank NUBAN Resolution & Account Activation
            elif profile.verification_status == 'APPROVED':
                bank_code = request.POST.get('bank_code', '').strip()
                bank_name = request.POST.get('bank_name', '').strip()
                account_number = request.POST.get('account_number', '').strip()

                if not (bank_code and account_number):
                    raise ValidationError("Please select your bank and enter your 10-digit account number.")

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

                        has_personal_name = (
                            personal_first and personal_last
                            and personal_first in account_name_clean
                            and personal_last in account_name_clean
                        )
                        has_business_name = (business_clean and business_clean in account_name_clean)

                        if not (has_personal_name or has_business_name):
                            messages.error(
                                request,
                                f"Bank Rejection: The account name returned by your bank is '{resolved_name}'. "
                                f"This does not match your registered identity ({request.user.get_full_name()}) "
                                f"or business name ({profile.business_name})."
                            )
                            return _safe_redirect('accounts:provider_status', 'provider_status')

                        with transaction.atomic():
                            profile.bank_code = bank_code
                            profile.bank_name = bank_name or profile.bank_name
                            profile.account_number = account_number
                            profile.account_name = resolved_name
                            profile.verification_status = 'ACTIVE'
                            if not profile.approved_at:
                                profile.approved_at = timezone.now()
                            profile.save()

                            request.user.role = 'PROVIDER'
                            request.user.is_verified = True
                            request.user.save(update_fields=['role', 'is_verified'])

                            VendorWallet.objects.get_or_create(provider=profile)

                        messages.success(request, f"Bank verified successfully as {resolved_name}! Welcome to AllThings.")
                        return redirect('dashboard:provider_dashboard')
                    else:
                        messages.error(request, "Invalid account number or bank selected. Please check and try again.")
                        return _safe_redirect('accounts:provider_status', 'provider_status')

                except Exception:
                    messages.error(request, "Could not reach the banking network at this time. Please try again later.")
                    return _safe_redirect('accounts:provider_status', 'provider_status')

        except ValidationError as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, error_msg)
            return _safe_redirect('accounts:provider_status', 'provider_status')

        return _safe_redirect('accounts:provider_status', 'provider_status')

    context = {'profile': profile}
    if profile.verification_status == 'APPROVED':
        banks = []
        try:
            headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
            banks_response = requests.get("https://api.paystack.co/bank?currency=NGN", headers=headers, timeout=8)
            if banks_response.status_code == 200:
                banks = banks_response.json().get('data', [])
        except requests.exceptions.RequestException:
            pass

        if not banks:
            banks = [
                {'name': 'Access Bank', 'code': '044'},
                {'name': 'First Bank of Nigeria', 'code': '011'},
                {'name': 'Guaranty Trust Bank (GTB)', 'code': '058'},
                {'name': 'Kuda Bank', 'code': '50211'},
                {'name': 'Moniepoint MFB', 'code': '50515'},
                {'name': 'OPay Digital Services', 'code': '999992'},
                {'name': 'Stanbic IBTC Bank', 'code': '221'},
                {'name': 'United Bank for Africa (UBA)', 'code': '033'},
                {'name': 'Zenith Bank', 'code': '057'},
            ]
        context['banks'] = banks

    return render(request, 'dashboard/provider_status.html', context)