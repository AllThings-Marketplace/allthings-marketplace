import hmac
import hashlib
import json
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db.models import F, Sum
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Order, OrderItem, JobBooking, ShippingAddress, Cart, CartItem, CartJobBooking, PaymentAttempt
from marketplace.models import Product, Service, ProductVariant
from .paystack import PaystackAPI
from .tasks import process_webhook_payment
from .utils import process_order_commissions, dispatch_gigl_rider, release_item_escrow, create_job_escrow, release_job_escrow

# --- 1. SHOPPING CART VIEWS ---

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    variant = None
    qty_to_add = 1

    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
        try:
            qty_to_add = int(request.POST.get('quantity', 1))
        except ValueError:
            qty_to_add = 1

    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart, 
        product=product,
        variant=variant,
        defaults={'quantity': 0}
    )
    
    available_stock = variant.stock if variant else product.stock_count
    
    if (cart_item.quantity + qty_to_add) <= available_stock:
        cart_item.quantity += qty_to_add
        cart_item.save()
        messages.success(request, f"{product.name} added to cart!")
    else:
        messages.error(request, f"Cannot add more. Only {available_stock} in stock.")
        
    return redirect('cart')

@login_required
def book_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    CartJobBooking.objects.get_or_create(cart=cart, service=service)
    messages.success(request, f"{service.name} has been added to your cart!")
    return redirect('home')

@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(customer=request.user)
    return render(request, 'cart.html', {'cart': cart})

@login_required
def remove_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    item.delete()
    return redirect('cart')

@login_required
def remove_job(request, job_id):
    job = get_object_or_404(CartJobBooking, id=job_id, cart__customer=request.user)
    job.delete()
    return redirect('cart')

@login_required
def clear_cart(request):
    cart = Cart.objects.filter(customer=request.user).first()
    if cart:
        cart.items.all().delete()
        cart.jobs.all().delete()
    return redirect('cart')

@login_required
def increase_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    available_stock = item.variant.stock if item.variant else item.product.stock_count
    
    if item.quantity < available_stock:
        item.quantity += 1
        item.save()
    else:
        messages.error(request, "Maximum available stock reached.")
    return redirect('cart')

@login_required
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete()
    return redirect('cart')


# --- 2. CHECKOUT & PAYMENT VIEWS ---

@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, customer=request.user)
    
    if not cart.items.exists() and not cart.jobs.exists():
        return redirect('home')

    saved_addresses = request.user.addresses.all().order_by('-is_default', '-created_at')

    if request.method == 'GET':
        selected_products = request.GET.getlist('selected_products')
        selected_services = request.GET.getlist('selected_services')
        
        if not selected_products and not selected_services:
            messages.error(request, "Please select at least one item to checkout.")
            return redirect('cart')

        checkout_items = cart.items.filter(id__in=selected_products)
        checkout_jobs = cart.jobs.filter(id__in=selected_services)
        
        total = sum(item.get_total for item in checkout_items) + sum(job.service.base_price for job in checkout_jobs)
        
        context = {
            'checkout_items': checkout_items,
            'checkout_jobs': checkout_jobs,
            'checkout_total': total,
            'selected_products': selected_products, 
            'selected_services': selected_services, 
            'saved_addresses': saved_addresses,
        }
        return render(request, 'checkout.html', context)

    if request.method == 'POST':
        selected_products = request.POST.getlist('selected_products')
        selected_services = request.POST.getlist('selected_services')
        
        checkout_items = cart.items.filter(id__in=selected_products)
        checkout_jobs = cart.jobs.filter(id__in=selected_services)
        
        for item in checkout_items:
            available_stock = item.variant.stock if item.variant else item.product.stock_count
            if item.quantity > available_stock:
                messages.error(request, f"Sorry, {item.product.name} just sold out. Please adjust your quantity.")
                return redirect('cart')

        # Create immutable Order snapshot
        order = Order.objects.create(customer=request.user, status='unpaid')
        
        selected_address_id = request.POST.get('selected_address')
        if selected_address_id and selected_address_id != 'new':
            address = get_object_or_404(ShippingAddress, id=selected_address_id, user=request.user)
            order.first_name = address.first_name
            order.last_name = address.last_name
            order.phone = address.phone
            order.alt_phone = address.alt_phone
            order.whatsapp = address.whatsapp
            order.region = address.region
            order.street_address = address.street_address
        else:
            order.first_name = request.POST.get('first_name')
            order.last_name = request.POST.get('last_name')
            order.phone = request.POST.get('phone')
            order.alt_phone = request.POST.get('alt_phone', '')
            order.whatsapp = request.POST.get('whatsapp', '')
            order.region = request.POST.get('region')
            order.street_address = request.POST.get('street_address')
            
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
                    is_default=not saved_addresses.exists()
                )

        total_amount = 0
        for c_item in checkout_items:
            price = c_item.variant.price_override if c_item.variant and c_item.variant.price_override else c_item.product.price
            OrderItem.objects.create(
                order=order,
                product=c_item.product,
                variant=c_item.variant,
                quantity=c_item.quantity,
                price=price,
                status='PENDING'
            )
            total_amount += (price * c_item.quantity)
            c_item.delete()

        scheduled_time = request.POST.get('scheduled_time')
        for c_job in checkout_jobs:
            JobBooking.objects.create(
                order=order,
                service=c_job.service,
                agreed_price=c_job.service.base_price,
                scheduled_time=scheduled_time if scheduled_time else None,
                service_address=f"{order.street_address}, {order.region}"
            )
            total_amount += c_job.service.base_price
            c_job.delete()

        order.total_amount = total_amount
        order.save()

        # Initialize Paystack
        paystack = PaystackAPI()
        dynamic_callback = request.build_absolute_uri(reverse('verify_payment'))
        
        response = paystack.initialize_transaction(
            email=request.user.email,
            amount=order.total_amount,
            order_id=order.id,
            callback_url=dynamic_callback
        )

        if response.get('status'):
            PaymentAttempt.objects.create(
                order=order,
                reference=response['data']['reference'],
                amount=order.total_amount,
                status='pending'
            )
            return redirect(response['data']['authorization_url'])
        else:
            messages.error(request, "Payment gateway unavailable. Please try again.")
            return redirect('cart')

@login_required
def verify_payment(request):
    reference = request.GET.get('reference')
    if not reference:
        return redirect('cart')

    paystack = PaystackAPI()
    response = paystack.verify_transaction(reference)

    if response.get('data') and response['data']['status'] == 'success':
        order_id = response['data']['metadata']['order_id']
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        # Log successful attempt
        PaymentAttempt.objects.filter(reference=reference).update(status='successful')
        
        # Check against new status model instead of is_paid
        if order.status == 'unpaid':
            order.status = 'confirmed'
            order.save(update_fields=['status'])
            
            for item in order.items.all():
                item.status = 'PAID'
                item.save(update_fields=['status'])
                item.generate_handshake_codes()
                
                if item.variant:
                    item.variant.stock = F('stock') - item.quantity
                    item.variant.save()
                
                if item.product:
                    item.product.stock_count = F('stock_count') - item.quantity
                    item.product.save()
            
            process_order_commissions(order)

        return redirect('order_success', order_id=order.id)
    
    # Log failed attempt
    PaymentAttempt.objects.filter(reference=reference).update(status='failed')
    return redirect('cart')

@csrf_exempt
def paystack_webhook(request):
    if request.method == 'POST':
        payload = request.body
        sig_header = request.headers.get('x-paystack-signature')
        secret_key = settings.PAYSTACK_SECRET_KEY.encode('utf-8')

        hash = hmac.new(secret_key, payload, hashlib.sha512).hexdigest()
        if hash != sig_header:
            return HttpResponse(status=400)

        event_data = json.loads(payload)
        
        if event_data.get('event') == 'charge.success':
            metadata = event_data['data'].get('metadata', {})
            order_id = metadata.get('order_id')
            
            if order_id:
                process_webhook_payment.delay(order_id, event_data['data']['reference'])

        return HttpResponse(status=200)
    return HttpResponse(status=405)


# --- 3. CUSTOMER DASHBOARD VIEWS ---

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_success.html', {'order': order})

@login_required
def order_history(request):
    if request.user.role == 'PROVIDER':
        return redirect('provider_dashboard')
        
    # Order Center Concept: Fetch ALL orders regardless of status
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})

@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_details.html', {'order': order})

@login_required
def confirm_item_delivery(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
        submitted_code = request.POST.get('delivery_code', '').strip()
        
        if item.status in ['DELIVERED', 'COMPLETED']:
            messages.info(request, "This item has already been marked as completed.")
            return redirect('order_details', order_id=item.order.id)
            
        if submitted_code == item.delivery_code:
            item.status = 'COMPLETED'
            item.save(update_fields=['status'])
            
            # Check if all items in the parent order are completed to update parent status
            all_completed = not item.order.items.exclude(status='COMPLETED').exists()
            if all_completed:
                item.order.status = 'completed'
                item.order.save(update_fields=['status'])
                
            release_item_escrow(item)
            messages.success(request, f"Delivery confirmed for {item.product.name}! The vendor has been credited.")
        else:
            messages.error(request, "Invalid delivery code. Please check the code provided for this item.")
            
    return redirect('order_details', order_id=item.order.id)


# --- 4. PROVIDER / VENDOR VIEWS ---

@login_required
def provider_dashboard(request):
    if request.user.role != 'PROVIDER':
        return HttpResponseForbidden("Only registered service provider can view this page.")
    
    available_jobs = JobBooking.objects.filter(status='PENDING', order__status='confirmed')
    my_jobs = JobBooking.objects.filter(provider=request.user)
    
    context = {
        'available_jobs': available_jobs,
        'my_jobs': my_jobs
    }
    return render(request, 'provider_dashboard.html', context)

@login_required
def available_jobs(request):
    jobs = JobBooking.objects.filter(
        order__status='confirmed', # Ensure parent order is actually paid
        provider__isnull=True,
        status='PENDING'
    ).order_by('-order__created_at')
    return render(request, 'available_jobs.html', {'jobs': jobs})

@login_required
def accept_job(request, job_id):
    if request.method == 'POST':
        job = get_object_or_404(JobBooking, id=job_id, provider__isnull=True, order__status='confirmed')
        
        job.provider = request.user
        job.status = 'ACCEPTED'
        job.save(update_fields=['provider', 'status'])
        
        job.generate_completion_code()
        create_job_escrow(job)
        
        messages.success(request, f"You have accepted the booking for {job.service.name}!")
        return redirect('provider_dashboard')
    return redirect('available_jobs')

@login_required
def update_job_status(request, job_id, new_status):
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
            messages.success(request, f"Job verified! NGN {job.agreed_price} has been credited to your wallet.")
        else:
            messages.error(request, "Invalid completion PIN. Please verify with the client.")
    return redirect('provider_dashboard')

@login_required
def vendor_orders(request):
    profile = getattr(request.user, 'provider_profile', None)
    
    if not profile or profile.provider_type not in ['VENDOR', 'BOTH']:
        messages.error(request, "Only product vendors can manage store orders.")
        return redirect('provider_dashboard')

    # Exclude unpaid orders from vendor view
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
    return redirect('vendor_orders')