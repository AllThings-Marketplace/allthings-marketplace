from django.db.models import F, Sum
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .models import Order, OrderItem, JobBooking, ShippingAddress
from marketplace.models import Product, Service, ProductVariant
from django.http import HttpResponseForbidden
from .paystack import PaystackAPI
from django.contrib import messages
from .utils import process_order_commissions
from django.utils import timezone
from .utils import process_order_commissions, dispatch_gigl_rider, release_item_escrow, create_job_escrow, release_job_escrow

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    order, created = Order.objects.get_or_create(customer=request.user, is_paid=False)
    
    # Default assumptions
    variant = None
    item_price = product.price
    qty_to_add = 1

    # Catch data if arriving from the Product Detail Page form
    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
            item_price = variant.price_override if variant.price_override else product.price
        
        # Safely parse quantity from form
        try:
            qty_to_add = int(request.POST.get('quantity', 1))
        except ValueError:
            qty_to_add = 1

    # Look for an exact match of BOTH the product AND the variant
    order_item, item_created = OrderItem.objects.get_or_create(
        order=order, 
        product=product,
        variant=variant,
        defaults={'price': item_price, 'quantity': 0}
    )
    
    # Calculate max available stock
    available_stock = variant.stock if variant else product.stock_count
    
    # Safely increase quantity without exceeding stock
    if (order_item.quantity + qty_to_add) <= available_stock:
        order_item.quantity += qty_to_add
        order_item.save()
        messages.success(request, f"{product.name} added to cart!")
    else:
        messages.error(request, f"Cannot add more. Only {available_stock} in stock.")
        
    return redirect('cart')

@login_required
def book_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    order, created = Order.objects.get_or_create(customer=request.user, is_paid=False)
    
    # Add the service to the order (defaults to PENDING status)
    JobBooking.objects.get_or_create(
        order=order,
        service=service,
        defaults={'service_address': 'Address pending checkout'}
    )

    messages.success(request, f"{service.name} has been added to your cart!")
    
    return redirect('home')

@login_required
def cart_view(request):
    # Fetch the user's active, unpaid order (using .first() to grab the single open order)
    order = Order.objects.filter(customer=request.user, is_paid=False).first()
    
    return render(request, 'cart.html', {'order': order})

@login_required
def checkout_view(request):
    order = Order.objects.filter(customer=request.user, is_paid=False).first()
    
    if not order or (not order.items.exists() and not order.job_bookings.exists()):
        return redirect('home')

    # Fetch the user's saved addresses
    saved_addresses = request.user.addresses.all().order_by('-is_default', '-created_at')

    # --- STEP 1: Handle arriving from the Cart (GET) ---
    if request.method == 'GET':
        selected_products = request.GET.getlist('selected_products')
        selected_services = request.GET.getlist('selected_services')
        
        if not selected_products and not selected_services:
            messages.error(request, "Please select at least one item to checkout.")
            return redirect('cart')

        checkout_items = order.items.filter(id__in=selected_products)
        checkout_jobs = order.job_bookings.filter(id__in=selected_services)
        
        total = sum(item.get_total for item in checkout_items) + sum(job.service.base_price for job in checkout_jobs)
        
        context = {
            'checkout_items': checkout_items,
            'checkout_jobs': checkout_jobs,
            'checkout_total': total,
            'selected_products': selected_products, 
            'selected_services': selected_services, 
            'saved_addresses': saved_addresses, # Pass addresses to the template
        }
        return render(request, 'checkout.html', context)

    # --- STEP 2: Handle submitting the Checkout Form (POST) ---
    if request.method == 'POST':
        selected_products = request.POST.getlist('selected_products')
        selected_services = request.POST.getlist('selected_services')
        
        checkout_items = order.items.filter(id__in=selected_products)
        checkout_jobs = order.job_bookings.filter(id__in=selected_services)
        
        # --- Stock Verification ---
        for item in checkout_items:
            available_stock = item.variant.stock if item.variant else item.product.stock_count
            if item.quantity > available_stock:
                messages.error(request, f"Sorry, {item.product.name} just sold out or stock was reduced. Please adjust your quantity.")
                return redirect('cart')
        
        # --- NEW: Handle Address Selection Logic ---
        selected_address_id = request.POST.get('selected_address')
        
        if selected_address_id and selected_address_id != 'new':
            # 1. User selected an existing saved address
            address = get_object_or_404(ShippingAddress, id=selected_address_id, user=request.user)
            order.first_name = address.first_name
            order.last_name = address.last_name
            order.phone = address.phone
            order.alt_phone = address.alt_phone
            order.whatsapp = address.whatsapp
            order.region = address.region
            order.street_address = address.street_address
        else:
            # 2. User typed a brand new address
            order.first_name = request.POST.get('first_name')
            order.last_name = request.POST.get('last_name')
            order.phone = request.POST.get('phone')
            order.alt_phone = request.POST.get('alt_phone', '')
            order.whatsapp = request.POST.get('whatsapp', '')
            order.region = request.POST.get('region')
            order.street_address = request.POST.get('street_address')
            
            # Save this new address to their address book for future use
            if order.street_address and order.region:
                ShippingAddress.objects.create(
                    user=request.user,
                    first_name=order.first_name,
                    last_name=order.last_name,
                    phone=order.phone,
                    alt_phone=order.alt_phone,
                    whatsapp=order.whatsapp,
                    region=order.region,
                    street_address=order.street_address,
                    is_default=not saved_addresses.exists() # Make it default if it's their first one
                )
        
        # Handle Service-Specific fields
        if checkout_jobs.exists():
            scheduled_time = request.POST.get('scheduled_time')
            for job in checkout_jobs:
                job.service_address = f"{order.street_address}, {order.region}"
                if scheduled_time:
                    job.scheduled_time = scheduled_time
                job.save()

        total_amount = sum(item.get_total for item in checkout_items) + sum(job.service.base_price for job in checkout_jobs)
        
        # Move unselected items to a brand new cart
        unselected_items = order.items.exclude(id__in=selected_products)
        unselected_jobs = order.job_bookings.exclude(id__in=selected_services)
        if unselected_items.exists() or unselected_jobs.exists():
            new_cart = Order.objects.create(customer=request.user, is_paid=False)
            unselected_items.update(order=new_cart)
            unselected_jobs.update(order=new_cart)

        # Lock in final details for Paystack
        order.total_amount = total_amount
        order.save()

        paystack = PaystackAPI()
        response = paystack.initialize_transaction(
            email=request.user.email,
            amount=order.total_amount,
            order_id=order.id
        )

        if response.get('status'):
            return redirect(response['data']['authorization_url'])
        else:
            messages.error(request, "Payment gateway unavailable. Please try again.")
            return redirect('cart')

@login_required
def verify_payment(request):
    # Paystack sends the transaction reference in the URL (e.g., ?reference=abc123xyz)
    reference = request.GET.get('reference')
    
    if not reference:
        return redirect('cart')

    paystack = PaystackAPI()
    response = paystack.verify_transaction(reference)

    # Check if Paystack confirms the transaction was successful
    if response.get('data') and response['data']['status'] == 'success':
        # Extract the order_id we passed into the metadata earlier
        order_id = response['data']['metadata']['order_id']
        
        # Find the order
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        # CRITICAL: Only process if it hasn't been paid yet to prevent double-crediting
        if not order.is_paid:
            order.is_paid = True
            order.save()
            
            # --- NEW: Shift physical items to PAID, generate OTPs, and Deduct Stock ---
            for item in order.items.all():
                item.status = 'PAID'
                item.save(update_fields=['status'])
                item.generate_handshake_codes()
                
                # Safe Stock Deduction: Variant specific
                if item.variant:
                    item.variant.stock = F('stock') - item.quantity
                    item.variant.save()
                
                # Safe Stock Deduction: Main product synchronization
                if item.product:
                    item.product.stock_count = F('stock_count') - item.quantity
                    item.product.save()
            # -----------------------------------------------------------
            
            # Automatically calculate the 10% split and route funds to pending balances
            process_order_commissions(order)

        return redirect('order_success', order_id=order.id)
        
    # If the payment failed or was abandoned, send them back to their cart
    return redirect('cart')

@login_required
def order_success(request, order_id):
    # Retrieve the specific completed order belonging to this user
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_success.html', {'order': order})

@login_required
def provider_dashboard(request):
    # Security check: Only let Providers see this page
    if request.user.role != 'PROVIDER':
        return HttpResponseForbidden("Only registered service provider can view this page.")
    
    # Grab jobs that no one has taken yet
    available_jobs = JobBooking.objects.filter(status='PENDING')
    
    # Grab jobs that belong to THIS specific logged-in service provider
    my_jobs = JobBooking.objects.filter(provider=request.user)
    
    context = {
        'available_jobs': available_jobs,
        'my_jobs': my_jobs
    }
    return render(request, 'provider_dashboard.html', context)

@login_required
def available_jobs(request):
    """Shows open, paid service jobs waiting for a technician."""
    jobs = JobBooking.objects.filter(
        order__is_paid=True,
        provider__isnull=True,
        status='PENDING'
    ).order_by('-order__created_at')
    return render(request, 'available_jobs.html', {'jobs': jobs})

@login_required
def accept_job(request, job_id):
    """Assigns an open job to the logged-in provider and initializes escrow."""
    if request.method == 'POST':
        job = get_object_or_404(JobBooking, id=job_id, provider__isnull=True, order__is_paid=True)
        
        job.provider = request.user
        job.status = 'ACCEPTED'
        job.save(update_fields=['provider', 'status'])
        
        # Generate the customer's completion verification PIN and lock escrow
        job.generate_completion_code()
        create_job_escrow(job)
        
        messages.success(request, f"You have accepted the booking for {job.service.name}!")
        return redirect('provider_dashboard')
        
    return redirect('available_jobs')

@login_required
def update_job_status(request, job_id, new_status):
    """Allows the assigned technician to mark themselves En Route."""
    if request.method == 'POST':
        job = get_object_or_404(JobBooking, id=job_id, provider=request.user)
        
        if job.status == 'ACCEPTED' and new_status == 'IN_PROGRESS':
            job.status = new_status
            job.save(update_fields=['status'])
            messages.success(request, "Status updated to In Progress.")
        else:
            messages.error(request, "Invalid status transition.")
            
    return redirect('provider_dashboard')

@login_required
def verify_job_completion(request, job_id):
    """Technician submits customer PIN upon finishing the job to trigger escrow payout."""
    if request.method == 'POST':
        job = get_object_or_404(JobBooking, id=job_id, provider=request.user)
        submitted_code = request.POST.get('completion_code', '').strip()
        
        if job.status == 'COMPLETED':
            messages.info(request, "This job has already been completed.")
            return redirect('provider_dashboard')
            
        if submitted_code == job.completion_code:
            job.status = 'COMPLETED'
            job.save(update_fields=['status'])
            
            release_job_escrow(job)
            messages.success(request, f"Job verified! NGN {job.service.base_price} has been credited to your wallet.")
        else:
            messages.error(request, "Invalid completion PIN. Please verify with the client.")
            
    return redirect('provider_dashboard')

@login_required
def order_history(request):
    # Security check: Ensure providers don't try to access customer history
    if request.user.role == 'PROVIDER':
        return redirect('provider_dashboard')
        
    # Fetch paid orders belonging to this user, ordered by newest first
    orders = Order.objects.filter(customer=request.user, is_paid=True).order_by('-created_at')
    
    return render(request, 'order_history.html', {'orders': orders})

@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_details.html', {'order': order})

@login_required
def remove_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)
    item.delete()
    return redirect('cart')

@login_required
def remove_job(request, job_id):
    job = get_object_or_404(JobBooking, id=job_id)
    job.delete()
    return redirect('cart')

@login_required
def clear_cart(request):
    # Updated to match your specific model fields: 'customer' and 'is_paid'
    order = Order.objects.filter(customer=request.user, is_paid=False).first()
    if order:
        order.items.all().delete()
        order.job_bookings.all().delete()
    return redirect('cart')

@login_required
def increase_quantity(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
    
    # Check the correct stock source
    available_stock = item.variant.stock if item.variant else item.product.stock_count
    
    if item.quantity < available_stock:
        item.quantity += 1
        item.save()
    else:
        messages.error(request, "Maximum available stock reached.")
        
    return redirect('cart')

@login_required
def decrease_quantity(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete() # Automatically remove it if they drop below 1
    return redirect('cart')

@login_required
def vendor_orders(request):
    profile = getattr(request.user, 'provider_profile', None)
    
    # Security: Ensure only vendors can access this
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only product vendors can manage store orders.")
        return redirect('provider_dashboard')

    # Fetch all paid order items belonging to this vendor
    vendor_items = OrderItem.objects.filter(
        product__provider=profile,
        order__is_paid=True
    )
    
    # --- NEW: Analytics Engine ---
    # 1. Calculate total gross revenue from completed sales
    total_revenue = vendor_items.filter(status='COMPLETED').aggregate(
        total=Sum(F('price') * F('quantity'))
    )['total'] or 0.00
    
    # Calculate net earnings (assuming your platform takes a 10% commission)
    net_earnings = float(total_revenue) * 0.90
    
    # 2. Count items that need immediate attention
    pending_fulfillment = vendor_items.filter(status__in=['PAID', 'ACCEPTED']).count()
    
    # 3. Low stock alerts (checking the main Product stock)
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
        # Security: Fetch the item but enforce that the logged-in user owns the product
        profile = getattr(request.user, 'provider_profile', None)
        item = get_object_or_404(OrderItem, id=item_id, product__provider=profile)
        
        # Define the exact buttons a vendor is allowed to click based on current state
        valid_transitions = {
            'PAID': ['ACCEPTED', 'CANCELLED'],
            'ACCEPTED': ['READY_FOR_PICKUP'],
        }
        
        current_status = item.status
        
        # Check if the requested move is legal
        if current_status in valid_transitions and new_status in valid_transitions[current_status]:
            item.status = new_status
            
            # --- NEW: Trigger GIGL API on pickup readiness ---
            if new_status == 'READY_FOR_PICKUP':
                # api_response = dispatch_gigl_rider(item)
                dispatch_gigl_rider(item)
                
                # Note: Once you have live GIGL API keys, you will map their response here:
                # if api_response and api_response.get('trackingNumber'):
                #     item.tracking_number = api_response['trackingNumber']
                #     item.rider_name = api_response.get('riderName', 'Pending Allocation')
                #     item.logistics_provider = 'GIGL'
            
            # Save all changes to the database
            item.save(update_fields=['status']) # Add 'tracking_number', 'rider_name' later
            messages.success(request, f"Order status updated to: {item.get_status_display()}")
        else:
            messages.error(request, "You cannot perform that action right now.")
            
    return redirect('vendor_orders')

@login_required
def confirm_item_delivery(request, item_id):
    if request.method == 'POST':
        # Ensure only the customer who placed the order can confirm it
        item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
        submitted_code = request.POST.get('delivery_code', '').strip()
        
        if item.status in ['DELIVERED', 'COMPLETED']:
            messages.info(request, "This item has already been marked as completed.")
            return redirect('order_details', order_id=item.order.id)
            
        # Verify the OTP matches the database
        if submitted_code == item.delivery_code:
            item.status = 'COMPLETED'
            item.save(update_fields=['status'])
            
            # Fire the utility function to unlock the vendor's money
            from .utils import release_item_escrow
            release_item_escrow(item)
            
            messages.success(request, f"Delivery confirmed for {item.product.name}! The vendor has been credited.")
        else:
            messages.error(request, "Invalid delivery code. Please check the code provided for this item.")
            
    return redirect('order_details', order_id=item.order.id)