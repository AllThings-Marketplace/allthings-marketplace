from django.db import IntegrityError
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.db.models import Avg, Count

from .forms import CustomerSignUpForm, UserUpdateForm
from .models import ProviderProfile, VendorWallet
from feedback.models import Feedback

@login_required(login_url='/accounts/login/')
def profile_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')
    else:
        form = UserUpdateForm(instance=request.user)
    
    avg_rating = 0
    review_count = 0
    star_percentage = "0%"
    recent_reviews = []

    if hasattr(request.user, 'provider_profile'):
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
    
    return render(request, 'register.html', {'form': form})


def custom_logout(request):
    logout(request)
    return redirect('marketplace:home')


@login_required
def apply_provider(request):
    if hasattr(request.user, 'provider_profile'):
        return redirect('provider_status') 

    if request.method == 'POST':
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
        )
        return redirect('provider_status')

    return render(request, 'provider_application.html')


@login_required
def provider_status(request):
    if not hasattr(request.user, 'provider_profile'):
        return redirect('apply_provider')
    
    profile = request.user.provider_profile
    
    if profile.verification_status == 'ACTIVE':
        # Updated to point to the new dashboard app
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
                response = requests.get(verify_url, headers=headers)
                res_data = response.json()
                
                if res_data.get('status'):
                    resolved_name = res_data['data']['account_name']
                    
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

                    profile.bank_name = bank_name
                    profile.account_number = account_number
                    profile.account_name = resolved_name 
                    
                    profile.verification_status = 'ACTIVE'
                    profile.save()
                    VendorWallet.objects.get_or_create(provider=profile)
                    
                    messages.success(request, f"Bank verified successfully as {resolved_name}! Welcome to All Things.")
                    # Updated to point to the new dashboard app
                    return redirect('dashboard:provider_dashboard')
                else:
                    messages.error(request, "Invalid account number or bank selected. Please check and try again.")
                    return redirect('provider_status')
                    
            except Exception as e:
                messages.error(request, "Could not reach the banking network at this time. Please try again later.")
                return redirect('provider_status')

        return redirect('provider_status')

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