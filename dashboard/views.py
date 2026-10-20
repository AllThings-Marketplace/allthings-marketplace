import uuid
import requests
from django.conf import settings
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import F, Q, Sum
from django.db import transaction
from django.core.exceptions import ValidationError

# Django Core & Auth
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Models from your other apps
from accounts.models import ProviderProfile, VendorWallet, VendorTransaction
from orders.models import Order, OrderItem, ServiceOrder, ServiceQuote, SupportTicket
from orders.paystack import PaystackAPI
from marketplace.models import (
    Product, Service, ProductImage, ServiceImage, 
    Category, ProductVariant, ServicePackage
)

# Utilities & AI Tasks
from orders.utils import dispatch_gigl_rider
from marketplace.tasks import (
    process_product_image_task, 
    process_service_cover_task, 
    process_service_portfolio_task
)
from marketplace.validators import validate_product_image 


# --- 1. MAIN DASHBOARD ---

@login_required
def provider_dashboard(request):
    profile = getattr(request.user, 'provider_profile', None)
    if not profile:
        return HttpResponseForbidden("Only registered service providers can view this page.")
    
    is_vendor = profile.provider_type in ['VENDOR', 'BOTH']
    is_service = profile.provider_type in ['SERVICE', 'BOTH']

    products = []
    pending_store_orders_count = 0
    low_stock_count = 0

    if is_vendor:
        products = profile.products.select_related('category').prefetch_related('images').order_by('-id')
        pending_store_orders_count = OrderItem.objects.filter(
            product__provider=profile,
            status__in=['PAID', 'ACCEPTED']
        ).exclude(order__status='unpaid').count()
        low_stock_count = profile.products.filter(stock_count__lt=5).count()
    
    my_services = []
    pending_requests = []
    active_jobs = []
    past_jobs = []
    
    if is_service:
        my_services = Service.objects.filter(provider=profile).select_related('category')
        pending_requests = ServiceOrder.objects.filter(
            provider=profile,
            status='REQUESTED'
        ).select_related('service', 'customer', 'package')
        
        active_jobs = ServiceOrder.objects.filter(
            provider=profile, 
            status__in=['QUOTE_SENT', 'ACCEPTED', 'PAID', 'IN_PROGRESS'] 
        ).select_related('service', 'customer').order_by('-created_at')
        
        past_jobs = ServiceOrder.objects.filter(
            provider=profile,
            status__in=['COMPLETED', 'CONFIRMED', 'DISPUTED', 'DECLINED', 'CANCELLED']
        ).select_related('service', 'customer').order_by('-updated_at')[:5]

    # Active Escrow Disputes / Support Tickets involving this provider
    active_disputes = SupportTicket.objects.filter(
        Q(order_item__product__provider=profile) | Q(service_order__provider=profile),
        status__in=['OPEN', 'IN_PROGRESS']
    ).select_related('order', 'order_item__product', 'service_order__service').distinct()[:5]
    
    # Wallet, Ledger History & Real-Time Withdrawal Eligibility
    wallet, _ = VendorWallet.objects.get_or_create(provider=profile)
    recent_transactions = VendorTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:8]

    days_left = 0
    last_payout = VendorTransaction.objects.filter(
        wallet=wallet,
        transaction_type='PAYOUT'
    ).order_by('-created_at').first()

    if last_payout:
        days_since = (timezone.now() - last_payout.created_at).days
        if days_since < 7:
            days_left = 7 - days_since

    has_bank_details = all([profile.account_name, profile.account_number, profile.bank_code])
    can_withdraw = (
        profile.verification_status == 'ACTIVE'
        and days_left == 0
        and wallet.available_balance >= Decimal('100.00')
        and has_bank_details
    )
    
    context = {
        'profile': profile,
        'wallet': wallet,
        'products': products,
        'my_services': my_services,
        'pending_requests': pending_requests,
        'active_jobs': active_jobs,
        'past_jobs': past_jobs,
        'active_disputes': active_disputes,
        'pending_store_orders_count': pending_store_orders_count,
        'low_stock_count': low_stock_count,
        'recent_transactions': recent_transactions, 
        'can_withdraw': can_withdraw,
        'days_left': days_left,
        'has_bank_details': has_bank_details,
    }
    return render(request, 'dashboard/provider_dashboard.html', context)


# --- 2. FINANCIALS ---

@login_required
def request_payout(request):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        
        if not profile or profile.verification_status != 'ACTIVE' or not hasattr(profile, 'wallet'):
            messages.error(request, "Your account is not eligible for withdrawals.")
            return redirect('dashboard:provider_dashboard')

        wallet = profile.wallet

        # Check weekly withdrawal limit
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
                return redirect('dashboard:provider_dashboard')
        
        # Verify provider has banking details set up
        if not all([profile.account_name, profile.account_number, profile.bank_code]):
            messages.error(request, "Please complete your bank details (including Bank Code) in your profile settings before withdrawing.")
            return redirect('dashboard:provider_dashboard')
        
        try:
            amount = Decimal(request.POST.get('amount'))
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Please enter a valid numeric amount.")
            return redirect('dashboard:provider_dashboard')

        if amount <= 0:
            messages.error(request, "Withdrawal amount must be greater than zero.")
        elif amount > wallet.available_balance:
            messages.error(request, "Insufficient funds.")
        else:
            paystack = PaystackAPI()
            unique_ref = f"WD-{uuid.uuid4().hex[:8].upper()}"
            
            recipient_response = paystack.create_transfer_recipient(
                name=profile.account_name,
                account_number=profile.account_number,
                bank_code=profile.bank_code
            )
            
            if not recipient_response.get('status'):
                messages.error(request, f"Bank Verification Failed: {recipient_response.get('message')}")
                return redirect('dashboard:provider_dashboard')
                
            recipient_code = recipient_response['data']['recipient_code']
            
            transfer_response = paystack.initiate_transfer(
                amount_in_naira=amount,
                recipient_code=recipient_code,
                reference=unique_ref,
                reason=f"AllThings Payout for {profile.business_name}"
            )
            
            if transfer_response.get('status'):
                with transaction.atomic():
                    wallet.available_balance -= amount
                    wallet.total_withdrawn += amount
                    wallet.save()

                    VendorTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='PAYOUT',
                        gross_amount=amount,
                        commission=Decimal('0.00'),
                        net_amount=amount,
                        reference=unique_ref,
                        status='PENDING'
                    )
                
                messages.success(request, "Withdrawal initiated successfully! The funds will reflect in your bank account shortly.")
            else:
                messages.error(request, f"Transfer Failed: {transfer_response.get('message')}")

    return redirect('dashboard:provider_dashboard')


# --- 3. LISTING MANAGEMENT (Products & Services) ---

@login_required
def add_product(request):
    profile = getattr(request.user, 'provider_profile', None)
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only vendors can add products.")
        return redirect('dashboard:provider_dashboard')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                category_id = request.POST.get('category_id')
                if not category_id:
                    raise ValidationError("Please select a product category.")
                category = Category.objects.get(id=category_id)

                dynamic_attributes = {}
                schema = category.attribute_schema
                
                if schema:
                    for attr in schema:
                        attr_name = attr.get('name', '')
                        is_required = attr.get('required', False)
                        expected_field_name = f"attr_{attr_name.lower().replace(' ', '_')}"
                        submitted_value = request.POST.get(expected_field_name, '').strip()
                        
                        if is_required and not submitted_value:
                            raise ValidationError(f"The specification '{attr_name}' is required for this category.")
                        if submitted_value:
                            dynamic_attributes[attr_name] = submitted_value

                uploaded_files = request.FILES.getlist('images')
                if not uploaded_files:
                    raise ValidationError("You must upload at least one product image.")

                # Logistics & Package Sizing Extraction
                shipping_class = request.POST.get('shipping_class', Product.ShippingClass.SMALL)
                if shipping_class not in dict(Product.ShippingClass.choices):
                    shipping_class = Product.ShippingClass.SMALL

                try:
                    weight_kg = Decimal(request.POST.get('weight_kg', '1.00'))
                    if weight_kg <= 0:
                        weight_kg = Decimal('1.00')
                except (InvalidOperation, TypeError, ValueError):
                    weight_kg = Decimal('1.00')

                product = Product.objects.create(
                    provider=profile,
                    category=category,
                    name=request.POST.get('name'),
                    price=request.POST.get('price'),
                    stock_count=request.POST.get('stock_count', 0),
                    shipping_class=shipping_class,
                    weight_kg=weight_kg,
                    description=request.POST.get('description', ''),
                    attributes=dynamic_attributes, 
                    status=Product.ProductStatus.PENDING, 
                    is_active=False 
                )

                variant_names = request.POST.getlist('variant_names[]')
                variant_values = request.POST.getlist('variant_values[]')
                variant_prices = request.POST.getlist('variant_prices[]')
                variant_stocks = request.POST.getlist('variant_stocks[]')

                has_variants = False
                total_variant_stock = 0

                for name, value, price, stock in zip(variant_names, variant_values, variant_prices, variant_stocks):
                    if name.strip() and value.strip():
                        has_variants = True
                        try:
                            safe_price = Decimal(price.strip()) if price.strip() else None
                        except InvalidOperation:
                            safe_price = None
                            
                        safe_stock = int(stock.strip()) if stock.strip().isdigit() else 0
                        total_variant_stock += safe_stock

                        ProductVariant.objects.create(
                            product=product,
                            attribute_name=name.strip(),
                            attribute_value=value.strip(),
                            price_override=safe_price,
                            stock=safe_stock
                        )

                if has_variants:
                    product.stock_count = total_variant_stock
                    product.save()

                for index, image_file in enumerate(uploaded_files):
                    new_image = ProductImage.objects.create(
                        product=product,
                        original_image=image_file,
                        processing_status='UPLOADED',
                        image_type='MAIN' if index == 0 else 'GALLERY'
                    )
                    process_product_image_task.delay(new_image.id)

            messages.success(request, f"Product submitted! {len(uploaded_files)} images are being optimized.")
            return redirect('dashboard:provider_dashboard')

        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
        except ValidationError as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Upload Error: {error_msg}")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    return render(request, 'dashboard/add_product.html', {'parent_categories': parent_categories})


@login_required
def upload_product_images(request, product_id):
    profile = getattr(request.user, 'provider_profile', None)
    product = get_object_or_404(Product, id=product_id, provider=profile)

    if request.method == 'POST':
        uploaded_files = request.FILES.getlist('images')
        
        if not uploaded_files:
            messages.error(request, "Please select at least one image to upload.")
            return redirect('dashboard:provider_dashboard')

        for image_file in uploaded_files:
            new_image = ProductImage.objects.create(
                product=product,
                original_image=image_file,
                processing_status='UPLOADED'
            )
            process_product_image_task.delay(new_image.id)
        
        messages.success(request, f"Successfully uploaded {len(uploaded_files)} image(s). Our system is optimizing them now.")
        return redirect('dashboard:provider_dashboard')
        
    return render(request, 'marketplace/upload_images.html', {'product': product})


@login_required
def add_service(request):
    profile = getattr(request.user, 'provider_profile', None)
    if not profile:
        messages.error(request, "Only registered providers can add services.")
        return redirect('dashboard:provider_dashboard')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                category = Category.objects.get(id=request.POST.get('category_id'))
                pricing_type = request.POST.get('pricing_type')
                
                included_list = [i.strip() for i in request.POST.get('whats_included', '').split(',') if i.strip()]
                excluded_list = [i.strip() for i in request.POST.get('whats_excluded', '').split(',') if i.strip()]

                base_price_raw = request.POST.get('base_price')
                base_price = Decimal(base_price_raw.strip()) if base_price_raw and pricing_type not in ['QUOTE', 'PACKAGES'] else None

                radius_raw = request.POST.get('service_radius_km')
                radius = int(radius_raw.strip()) if radius_raw and radius_raw.strip().isdigit() else None

                cover_image = request.FILES.get('cover_image')
                if not cover_image:
                    raise ValidationError("A cover image is required.")

                service = Service.objects.create(
                    provider=profile,
                    category=category,
                    name=request.POST.get('name'),
                    description=request.POST.get('description'),
                    service_mode=request.POST.get('service_mode'),
                    service_radius_km=radius,
                    pricing_type=pricing_type,
                    base_price=base_price,
                    whats_included=included_list,
                    whats_excluded=excluded_list,
                    cover_image=cover_image
                )

                if pricing_type == 'PACKAGES':
                    pkg_names = request.POST.getlist('pkg_names[]')
                    pkg_prices = request.POST.getlist('pkg_prices[]')
                    pkg_durations = request.POST.getlist('pkg_durations[]')
                    pkg_features = request.POST.getlist('pkg_features[]')

                    for name, price, dur, feat in zip(pkg_names, pkg_prices, pkg_durations, pkg_features):
                        if name.strip() and price.strip():
                            ServicePackage.objects.create(
                                service=service,
                                name=name.strip(),
                                price=Decimal(price.strip()),
                                estimated_duration=dur.strip(),
                                features=[f.strip() for f in feat.split(',') if f.strip()]
                            )

                portfolio_files = request.FILES.getlist('portfolio_images')
                portfolio_ids = []
                
                for p_file in portfolio_files:
                    s_img = ServiceImage.objects.create(service=service, image=p_file)
                    portfolio_ids.append(s_img.id)

            transaction.on_commit(lambda: process_service_cover_task.delay(service.id))
            
            for pid in portfolio_ids:
                transaction.on_commit(lambda: process_service_portfolio_task.delay(pid))

            messages.success(request, "Service published! Your images are being optimized in the background.")
            return redirect('dashboard:provider_dashboard')

        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
        except ValidationError as e:
            error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
            messages.error(request, f"Upload Error: {error_msg}")
        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")

    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    return render(request, 'dashboard/add_service.html', {'parent_categories': parent_categories})


@login_required
def edit_service(request, service_id):
    profile = getattr(request.user, 'provider_profile', None)
    service = get_object_or_404(Service, id=service_id, provider=profile)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                category_id = request.POST.get('category_id')
                if category_id:
                    service.category_id = category_id
                
                service.name = request.POST.get('name', service.name)
                service.description = request.POST.get('description', service.description)
                
                submitted_mode = request.POST.get('service_mode', service.service_mode)
                if submitted_mode in dict(Service.ServiceMode.choices):
                    service.service_mode = submitted_mode
                
                radius_raw = request.POST.get('service_radius_km', '').strip()
                service.service_radius_km = int(radius_raw) if radius_raw.isdigit() else None
                
                included_raw = request.POST.get('whats_included', '')
                service.whats_included = [i.strip() for i in included_raw.split(',') if i.strip()]
                    
                excluded_raw = request.POST.get('whats_excluded', '')
                service.whats_excluded = [i.strip() for i in excluded_raw.split(',') if i.strip()]

                base_price_raw = request.POST.get('base_price')
                if base_price_raw and service.pricing_type not in ['QUOTE', 'PACKAGES']:
                    service.base_price = Decimal(base_price_raw.strip())

                new_cover = request.FILES.get('cover_image')
                if new_cover:
                    service.cover_image = new_cover
                    transaction.on_commit(lambda: process_service_cover_task.delay(service.id))

                service.save()
                messages.success(request, f"'{service.name}' was updated successfully!")
                return redirect('dashboard:provider_dashboard')

        except Exception as e:
            messages.error(request, f"Error updating service: {str(e)}")

    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    
    context = {
        'service': service,
        'parent_categories': parent_categories
    }
    return render(request, 'dashboard/edit_service.html', context)


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, provider=request.user.provider_profile)
    
    if request.method == 'POST':
        product.name = request.POST.get('name', product.name).strip()
        category_id = request.POST.get('category_id')
        if category_id:
            product.category_id = category_id
        product.price = request.POST.get('price', product.price)
        
        stock_input = request.POST.get('stock_count', '').strip()
        product.stock_count = int(stock_input) if stock_input.isdigit() else 0

        shipping_class = request.POST.get('shipping_class', product.shipping_class)
        if shipping_class in dict(Product.ShippingClass.choices):
            product.shipping_class = shipping_class

        try:
            weight_val = Decimal(request.POST.get('weight_kg', product.weight_kg))
            if weight_val > 0:
                product.weight_kg = weight_val
        except (InvalidOperation, TypeError, ValueError):
            pass
        
        product.description = request.POST.get('description', product.description)
        
        product.save()
        messages.success(request, f"'{product.name}' has been updated successfully.")
        return redirect('dashboard:provider_dashboard')

    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    
    context = {
        'product': product,
        'parent_categories': parent_categories,
    }
    return render(request, 'dashboard/edit_product.html', context)


# --- 4. VENDOR & SERVICE CONTRACT ACTIONS ---

@login_required
def vendor_orders(request):
    profile = getattr(request.user, 'provider_profile', None)
    
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only product vendors can manage store orders.")
        return redirect('dashboard:provider_dashboard')

    vendor_items = OrderItem.objects.filter(
        product__provider=profile
    ).exclude(order__status='unpaid').select_related('order', 'product', 'variant')
    
    total_revenue = vendor_items.filter(status='COMPLETED').aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0.00
    
    net_earnings = float(total_revenue) * 0.90
    pending_fulfillment = vendor_items.filter(status__in=['PAID', 'ACCEPTED']).count()
    low_stock_alerts = Product.objects.filter(provider=profile, stock_count__lt=5)

    context = {
        'vendor_items': vendor_items.order_by('-order__created_at'),
        'total_revenue': total_revenue,
        'net_earnings': net_earnings,
        'pending_fulfillment': pending_fulfillment,
        'low_stock_alerts': low_stock_alerts,
    }
    return render(request, 'dashboard/vendor_orders.html', context)


@login_required
def update_item_status(request, item_id, new_status):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        item = get_object_or_404(OrderItem, id=item_id, product__provider=profile)
        
        valid_transitions = {
            'PAID': ['ACCEPTED', 'CANCELLED'],
            'ACCEPTED': ['READY_FOR_PICKUP'],
        }
        
        current_status = item.status
        
        if current_status in valid_transitions and new_status in valid_transitions[current_status]:
            item.status = new_status
            
            if new_status == 'READY_FOR_PICKUP':
                dispatch_gigl_rider(item)
            
            item.save(update_fields=['status'])
            messages.success(request, f"Order status updated to: {item.get_status_display()}")
        else:
            messages.error(request, "You cannot perform that action right now.")
    return redirect('dashboard:vendor_orders')


@login_required
def accept_service_request(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='REQUESTED')
        
        service_order.status = 'ACCEPTED'
        service_order.save(update_fields=['status'])
        
        messages.success(request, f"You accepted the request for {service_order.service.name}. The customer has been notified to make payment.")
    return redirect('dashboard:provider_dashboard')


@login_required
def decline_service_request(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='REQUESTED')
        
        service_order.status = 'DECLINED'
        service_order.save(update_fields=['status'])
        
        messages.info(request, f"You declined the request for {service_order.service.name}.")
    return redirect('dashboard:provider_dashboard')


@login_required
def provider_start_service(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='PAID')
        
        service_order.status = 'IN_PROGRESS'
        service_order.save(update_fields=['status'])
        
        messages.success(request, f"You have started work on '{service_order.service.name}'.")
    return redirect('dashboard:provider_dashboard')


@login_required
def provider_complete_service(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='IN_PROGRESS')
        
        service_order.status = 'COMPLETED'
        service_order.completed_at = timezone.now()
        service_order.save(update_fields=['status', 'completed_at'])
        
        messages.success(request, f"You marked '{service_order.service.name}' as completed. Waiting for customer confirmation.")
    return redirect('dashboard:provider_dashboard')


@login_required
def send_quote(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='REQUESTED')
        
        labor_cost = request.POST.get('labor_cost', 0)
        materials_cost = request.POST.get('materials_cost', 0)
        provider_notes = request.POST.get('provider_notes', '')

        try:
            quote = ServiceQuote.objects.create(
                order=service_order,
                labor_cost=Decimal(str(labor_cost or 0)),
                materials_cost=Decimal(str(materials_cost or 0)),
                provider_notes=provider_notes
            )
            
            service_order.status = 'QUOTE_SENT'
            service_order.agreed_price = quote.total_amount
            service_order.save(update_fields=['status', 'agreed_price'])

            messages.success(request, f"Quote for NGN {quote.total_amount:,.2f} sent to the customer!")
            
        except Exception as e:
            messages.error(request, f"Error generating quote: {str(e)}")

    return redirect('dashboard:provider_dashboard')

@login_required
def provider_settings(request):
    """
    Dedicated Provider Settings Hub:
    1. Public Storefront & Branding (Bio, Category, Phone, Store Banner)
    2. Origin Dispatch Base & GPS Coordinates (Powers LogisticsEngine shipping quotes)
    3. Password-Protected + Paystack-Verified Payout Bank Account
    """
    if not hasattr(request.user, 'provider_profile'):
        return redirect('accounts:profile')

    profile = request.user.provider_profile
    if profile.verification_status != 'ACTIVE':
        return redirect('accounts:profile')

    if request.method == 'POST':
        section = request.POST.get('section', 'storefront')

        # 1. Public Storefront & Branding
        if section == 'storefront':
            profile.business_category = request.POST.get('business_category', '').strip()
            profile.phone = request.POST.get('phone', '').strip()
            profile.business_description = request.POST.get('business_description', '').strip()

            if 'exterior_image' in request.FILES:
                profile.exterior_image = request.FILES['exterior_image']

            profile.save()
            messages.success(request, "Public storefront settings updated!")
            return redirect('dashboard:provider_settings')

        # 2. Dispatch Base & GPS Coordinates
        elif section == 'location':
            region = request.POST.get('region', '').strip()
            store_address = request.POST.get('store_address', '').strip()
            lat = request.POST.get('latitude', '').strip()
            lon = request.POST.get('longitude', '').strip()

            if not (region and store_address):
                messages.error(request, "Both your Dispatch State/Region and Physical Address are required for courier rate calculation.")
                return redirect('dashboard:provider_settings')

            profile.region = region
            profile.store_address = store_address
            if lat and lon:
                try:
                    profile.latitude = float(lat)
                    profile.longitude = float(lon)
                except ValueError:
                    pass
            profile.save()
            messages.success(request, f"Dispatch hub updated to {region}. All checkout shipping quotes will now calculate from this location.")
            return redirect('dashboard:provider_settings')

        # 3. Protected Payout Bank Update (Requires Current Password + Paystack Name Match)
        elif section == 'payout':
            current_password = request.POST.get('current_password', '')
            bank_code = request.POST.get('bank_code', '').strip()
            bank_name = request.POST.get('bank_name', '').strip()
            account_number = request.POST.get('account_number', '').strip()

            if not request.user.check_password(current_password):
                messages.error(request, "Security Check Failed: Incorrect account password. Payout bank was not changed.")
                return redirect('dashboard:provider_settings')

            if not (bank_code and account_number):
                messages.error(request, "Please select a bank and enter a valid 10-digit account number.")
                return redirect('dashboard:provider_settings')

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
                            f"KYC Mismatch: Your bank returned '{resolved_name}', which does not match your verified name ({request.user.get_full_name()}) or business name ({profile.business_name})."
                        )
                        return redirect('dashboard:provider_settings')

                    profile.bank_name = bank_name or profile.bank_name
                    profile.account_number = account_number
                    profile.account_name = resolved_name
                    profile.save(update_fields=['bank_name', 'account_number', 'account_name'])
                    VendorWallet.objects.get_or_create(provider=profile)

                    messages.success(request, f"Payout account verified and updated to {resolved_name} ({profile.bank_name}).")
                else:
                    messages.error(request, "Paystack could not resolve that account number. Please double-check your 10-digit NUBAN.")
            except Exception:
                messages.error(request, "Unable to reach the banking verification service right now. Please try again shortly.")

            return redirect('dashboard:provider_settings')

    # Fetch Nigerian Banks from Paystack (with offline fallback)
    banks = []
    try:
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        banks_response = requests.get("https://api.paystack.co/bank?currency=NGN", headers=headers, timeout=6)
        if banks_response.status_code == 200:
            banks = banks_response.json().get('data', [])
    except Exception:
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

    return render(request, 'dashboard/provider_settings.html', {
        'profile': profile,
        'banks': banks,
    })