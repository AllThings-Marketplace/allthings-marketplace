import uuid
from django.db import IntegrityError
import requests
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import CustomerSignUpForm, UserUpdateForm
from .models import ProviderProfile, VendorWallet, VendorTransaction
from django.db.models import Avg, Count
from feedback.models import Feedback

@login_required(login_url='/accounts/login/')
def profile_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    # Calculate average rating and fetch reviews
    avg_rating = 0
    review_count = 0
    star_percentage = "0%"
    recent_reviews = []

    if hasattr(request.user, 'provider_profile'):
        # FIX: Pass request.user instead of the provider_profile
        stats = Feedback.objects.filter(
            target_provider=request.user, 
            is_verified=True
        ).aggregate(
            average_score=Avg('overall_rating'),
            total_reviews=Count('id')
        )
        
        avg_rating = stats['average_score'] or 0
        review_count = stats['total_reviews']
        star_percentage = f"{(avg_rating / 5) * 100}%"

        # FIX: Pass request.user here as well
        recent_reviews = Feedback.objects.filter(
            target_provider=request.user, 
            is_verified=True
        ).select_related('customer').order_by('-created_at')[:10]

    context = {
        'form': form,
        'avg_rating': round(avg_rating, 1),
        'review_count': review_count,
        'star_percentage': star_percentage,
        'recent_reviews': recent_reviews,
    }
    
    return render(request, 'profile.html', context)

def register_customer(request):
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST)
        if form.is_valid():
            try:
                # commit=False pauses the save so we can attach the custom role
                user = form.save(commit=False)
                user.role = 'CUSTOMER'
                user.save()
                
                # Automatically log them in after signing up
                login(request, user)
                return redirect('home')
                
            except IntegrityError:
                # Safely catches the database constraint crash you just experienced
                messages.error(request, "That username is already taken. Please choose another.")
        else:
            # If the form fails validation (e.g., short password), display the errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = CustomerSignUpForm()
    
    return render(request, 'register.html', {'form': form})

def custom_logout(request):
    logout(request)
    return redirect('home')

@login_required
def apply_provider(request):
    # Security: Prevent duplicate applications
    if hasattr(request.user, 'provider_profile'):
        return redirect('provider_status') 

    if request.method == 'POST':
        # Screen 1: Save User & Basic Business Data
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.save()

        ProviderProfile.objects.create(
            user=request.user,
            phone=request.POST.get('phone'),
            dob=request.POST.get('dob'),
            residential_address=request.POST.get('residential_address'),
            business_name=request.POST.get('business_name'),
            provider_type=request.POST.get('provider_type'),
            business_category=request.POST.get('business_category'),
            # Defaults to 'STAGE_1_BASIC'
        )
        return redirect('provider_status')

    return render(request, 'provider_application.html')

@login_required
def provider_status(request):
    # Gateway Checks
    if not hasattr(request.user, 'provider_profile'):
        return redirect('apply_provider')
    
    profile = request.user.provider_profile
    
    if profile.verification_status == 'ACTIVE':
        return redirect('provider_dashboard')

    # The Smart Router: Processes data based on current stage
    if request.method == 'POST':
        
        # Screen 2: KYC Submission
        if profile.verification_status == 'STAGE_1_BASIC':
            profile.id_type = request.POST.get('id_type')
            if 'id_document' in request.FILES:
                profile.id_document = request.FILES['id_document']
            if 'selfie_image' in request.FILES:
                profile.selfie_image = request.FILES['selfie_image']
                
            profile.verification_status = 'STAGE_2_KYC'
            profile.save()
            messages.success(request, "Documents Submitted Successfully.")
            
        # Screen 3: Business Submission
        elif profile.verification_status == 'STAGE_2_KYC':
            profile.business_description = request.POST.get('business_description')
            profile.cac_registration_number = request.POST.get('cac_registration_number')
            if 'business_certificate' in request.FILES:
                profile.business_certificate = request.FILES['business_certificate']
                
            profile.verification_status = 'STAGE_3_BUSINESS'
            profile.save()
            messages.success(request, "Business details recorded.")

        # Screen 4: Location Submission
        elif profile.verification_status == 'STAGE_3_BUSINESS':
            profile.region = request.POST.get('region')
            profile.store_address = request.POST.get('store_address')
            profile.latitude = request.POST.get('latitude')
            profile.longitude = request.POST.get('longitude')
            
            if 'exterior_image' in request.FILES:
                profile.exterior_image = request.FILES['exterior_image']
            if 'interior_image' in request.FILES:
                profile.interior_image = request.FILES['interior_image']
            if 'signboard_image' in request.FILES:
                profile.signboard_image = request.FILES['signboard_image']
                
            profile.verification_status = 'STAGE_4_LOCATION'
            profile.save()
            messages.success(request, "Location pinned! Your application is now under admin review.")

        # Screen 5: Payout Setup via Paystack API
        elif profile.verification_status == 'APPROVED':
            bank_code = request.POST.get('bank_code')
            bank_name = request.POST.get('bank_name') # Captured via hidden JS field
            account_number = request.POST.get('account_number')

            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            verify_url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"
            
            try:
                response = requests.get(verify_url, headers=headers)
                res_data = response.json()
                
                if res_data.get('status'):
                    # Paystack successfully found the account
                    resolved_name = res_data['data']['account_name']
                    
                    # 1. Smart Name Verification against the bank's official record
                    account_name_clean = resolved_name.strip().lower()
                    personal_first = request.user.first_name.strip().lower()
                    personal_last = request.user.last_name.strip().lower()
                    business_clean = profile.business_name.strip().lower()

                    has_personal_name = (personal_first in account_name_clean and personal_last in account_name_clean)
                    has_business_name = (business_clean in account_name_clean)

                    if not (has_personal_name or has_business_name):
                        messages.error(
                            request, 
                            f"Bank Rejection: The account name returned by your bank is '{resolved_name}'. This does not match your registered identity or business name."
                        )
                        return redirect('provider_status')

                    # 2. Save the Paystack-verified data and Activate
                    profile.bank_name = bank_name
                    profile.account_number = account_number
                    profile.account_name = resolved_name # Securely saving the bank's official record
                    
                    profile.verification_status = 'ACTIVE'
                    profile.save()
                    VendorWallet.objects.get_or_create(provider=profile)
                    
                    messages.success(request, f"Bank verified successfully as {resolved_name}! Welcome to All Things.")
                    return redirect('provider_dashboard')
                else:
                    messages.error(request, "Invalid account number or bank selected. Please check and try again.")
                    return redirect('provider_status')
                    
            except Exception as e:
                messages.error(request, "Could not reach the banking network at this time. Please try again later.")
                return redirect('provider_status')

        return redirect('provider_status')

    # GET Request: Fetch live banks if they are at the Payout stage
    context = {'profile': profile}
    if profile.verification_status == 'APPROVED':
        try:
            headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
            banks_response = requests.get("https://api.paystack.co/bank?currency=NGN", headers=headers)
            if banks_response.status_code == 200:
                context['banks'] = banks_response.json().get('data', [])
        except requests.exceptions.RequestException:
            context['banks'] = []

    return render(request, 'provider_status.html', context)

@login_required
def provider_dashboard(request):
    # Route 1: No application exists
    if not hasattr(request.user, 'provider_profile'):
        return redirect('apply_provider')
    
    profile = request.user.provider_profile
    
    # Route 2: Application is still under review
    if profile.verification_status != 'ACTIVE':
        return redirect('provider_status')
    
    # Route 3: Fully Active Provider
    wallet = profile.wallet
    recent_transactions = wallet.transactions.all().order_by('-created_at')[:5]

    # Calculate Weekly Cooldown for Withdrawals
    can_withdraw = True
    days_left = 0

    last_payout = VendorTransaction.objects.filter(
        wallet=wallet, 
        transaction_type='PAYOUT'
    ).order_by('-created_at').first()

    if last_payout:
        days_since = (timezone.now() - last_payout.created_at).days
        if days_since < 7:
            can_withdraw = False
            days_left = 7 - days_since

    context = {
        'profile': profile,
        'wallet': wallet,
        'recent_transactions': recent_transactions,
        'can_withdraw': can_withdraw,
        'days_left': days_left,
    }
    return render(request, 'provider_dashboard.html', context)

@login_required
def request_payout(request):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        
        if not profile or profile.verification_status != 'ACTIVE' or not hasattr(profile, 'wallet'):
            messages.error(request, "Your account is not eligible for withdrawals.")
            return redirect('provider_dashboard')

        wallet = profile.wallet

        # --- THE WEEKLY LOCK LOGIC ---
        last_payout = VendorTransaction.objects.filter(
            wallet=wallet, 
            transaction_type='PAYOUT'
        ).order_by('-created_at').first()

        if last_payout:
            days_since_last_payout = (timezone.now() - last_payout.created_at).days
            if days_since_last_payout < 7:
                days_left = 7 - days_since_last_payout
                messages.error(
                    request, 
                    f"Withdrawals are limited to once per week. You can request your next payout in {days_left} day(s)."
                )
                return redirect('provider_dashboard')
        # -----------------------------
        
        try:
            amount = Decimal(request.POST.get('amount'))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Please enter a valid numeric amount.")
            return redirect('provider_dashboard')

        if amount <= 0:
            messages.error(request, "Withdrawal amount must be greater than zero.")
        elif amount > wallet.available_balance:
            messages.error(request, "Insufficient funds.")
        else:
            wallet.available_balance -= amount
            wallet.save()

            unique_ref = f"WD-{uuid.uuid4().hex[:8].upper()}"
            VendorTransaction.objects.create(
                wallet=wallet,
                transaction_type='PAYOUT',
                gross_amount=amount,
                commission=Decimal('0.00'),
                net_amount=amount,
                reference=unique_ref,
                status='PENDING' 
            )
            
            messages.success(request, f"Withdrawal request submitted! Reference: {unique_ref}")

    return redirect('provider_dashboard')