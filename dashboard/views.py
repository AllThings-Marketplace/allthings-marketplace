import uuid
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db.models import F, Sum
from django.db import transaction
from django.core.exceptions import ValidationError

# Django Core & Auth
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Models from your other apps
from accounts.models import ProviderProfile, VendorWallet, VendorTransaction
from orders.models import Order, OrderItem, ServiceOrder, ServiceQuote
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
    
    products = profile.products.all() if profile.provider_type in ['VENDOR', 'BOTH'] else []
    
    my_services = []
    pending_requests = []
    active_jobs = []
    past_jobs = [] # NEW: Added to hold completed history
    
    if profile.provider_type in ['SERVICE', 'BOTH']:
        my_services = Service.objects.filter(provider=profile)
        pending_requests = ServiceOrder.objects.filter(provider=profile, status='REQUESTED')
        
        # UPDATED: Added QUOTE_SENT so quotes stay visible
        active_jobs = ServiceOrder.objects.filter(
            provider=profile, 
            status__in=['QUOTE_SENT', 'ACCEPTED', 'PAID', 'IN_PROGRESS'] 
        ).order_by('-created_at')
        
        # NEW: Query for recently finished/closed jobs
        past_jobs = ServiceOrder.objects.filter(
            provider=profile,
            status__in=['COMPLETED', 'CONFIRMED', 'DISPUTED', 'DECLINED', 'CANCELLED']
        ).order_by('-updated_at')[:5]
    
    wallet = profile.wallet if hasattr(profile, 'wallet') else {'available_balance': '0.00', 'pending_balance': '0.00'}
    
    context = {
        'profile': profile,
        'wallet': wallet,
        'products': products,
        'my_services': my_services,
        'pending_requests': pending_requests,
        'active_jobs': active_jobs,
        'past_jobs': past_jobs, # NEW: Passed to template
        'recent_transactions': [], 
        'can_withdraw': False,
        'days_left': 7,
    }
    return render(request, 'provider_dashboard.html', context)


# --- 2. FINANCIALS ---

@login_required
def request_payout(request):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        
        if not profile or profile.verification_status != 'ACTIVE' or not hasattr(profile, 'wallet'):
            messages.error(request, "Your account is not eligible for withdrawals.")
            return redirect('dashboard:provider_dashboard')

        wallet = profile.wallet

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
                    
                # for image_file in uploaded_files:
                #     validate_product_image(image_file) 

                product = Product.objects.create(
                    provider=profile,
                    category=category,
                    name=request.POST.get('name'),
                    price=request.POST.get('price'),
                    stock_count=request.POST.get('stock_count', 0),
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
    return render(request, 'add_product.html', {'parent_categories': parent_categories})

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
    return render(request, 'add_service.html', {'parent_categories': parent_categories})

@login_required
def edit_service(request, service_id):
    profile = getattr(request.user, 'provider_profile', None)
    
    # Security: Ensure the provider owns this specific service
    service = get_object_or_404(Service, id=service_id, provider=profile)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update Category
                category_id = request.POST.get('category_id')
                if category_id:
                    service.category_id = category_id
                
                # Update Core Fields
                service.name = request.POST.get('name', service.name)
                service.description = request.POST.get('description', service.description)
                service.service_mode = request.POST.get('service_mode', service.service_mode)
                
                radius_raw = request.POST.get('service_radius_km')
                if radius_raw and radius_raw.strip().isdigit():
                    service.service_radius_km = int(radius_raw.strip())
                
                # Update Inclusions/Exclusions
                included_raw = request.POST.get('whats_included')
                if included_raw:
                    service.whats_included = [i.strip() for i in included_raw.split(',') if i.strip()]
                    
                excluded_raw = request.POST.get('whats_excluded')
                if excluded_raw:
                    service.whats_excluded = [i.strip() for i in excluded_raw.split(',') if i.strip()]

                # Handle Pricing Updates (if fixed/starting price)
                base_price_raw = request.POST.get('base_price')
                if base_price_raw and service.pricing_type not in ['QUOTE', 'PACKAGES']:
                    service.base_price = Decimal(base_price_raw.strip())

                # Handle optional Cover Image update
                new_cover = request.FILES.get('cover_image')
                if new_cover:
                    service.cover_image = new_cover
                    # Trigger your AI background task for the new image
                    transaction.on_commit(lambda: process_service_cover_task.delay(service.id))

                service.save()
                messages.success(request, f"'{service.name}' was updated successfully!")
                return redirect('dashboard:provider_dashboard')

        except Exception as e:
            messages.error(request, f"Error updating service: {str(e)}")

    # For the GET request, fetch categories to populate the dropdown
    parent_categories = Category.objects.filter(parent__isnull=True, is_active=True)
    
    context = {
        'service': service,
        'parent_categories': parent_categories
    }
    return render(request, 'edit_service.html', context)


# --- 4. VENDOR & SERVICE CONTRACT ACTIONS ---

@login_required
def vendor_orders(request):
    profile = getattr(request.user, 'provider_profile', None)
    
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only product vendors can manage store orders.")
        return redirect('dashboard:provider_dashboard')

    vendor_items = OrderItem.objects.filter(
        product__provider=profile
    ).exclude(order__status='unpaid')
    
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
    return render(request, 'vendor_orders.html', context)

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
        service_order.save(update_fields=['status'])
        
        messages.success(request, f"You marked '{service_order.service.name}' as completed. Waiting for customer confirmation.")
    return redirect('dashboard:provider_dashboard')

@login_required
def send_quote(request, order_id):
    if request.method == 'POST':
        profile = getattr(request.user, 'provider_profile', None)
        
        # Security Check: Only find REQUESTED orders that belong to this exact provider
        service_order = get_object_or_404(ServiceOrder, id=order_id, provider=profile, status='REQUESTED')
        
        # Grab the values from the form (default to 0 if left blank)
        labor_cost = request.POST.get('labor_cost', 0)
        materials_cost = request.POST.get('materials_cost', 0)
        provider_notes = request.POST.get('provider_notes', '')

        try:
            # Create the quote in the database
            quote = ServiceQuote.objects.create(
                order=service_order,
                labor_cost=labor_cost,
                materials_cost=materials_cost,
                provider_notes=provider_notes
            )
            
            # Update the order status and set the agreed_price so Paystack knows what to charge later
            service_order.status = 'QUOTE_SENT'
            service_order.agreed_price = quote.total_amount
            service_order.save(update_fields=['status', 'agreed_price'])

            messages.success(request, f"Quote for NGN {quote.total_amount} sent to the customer!")
            
        except Exception as e:
            messages.error(request, f"Error generating quote: {str(e)}")

    return redirect('dashboard:provider_dashboard')