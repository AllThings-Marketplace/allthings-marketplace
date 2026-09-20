import hmac
import hashlib
import json
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db.models import F
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Order, OrderItem, ShippingAddress, Cart, CartItem, PaymentAttempt, ServiceOrder, OrderMessage, ServiceDispute
from marketplace.models import Product, Service, ProductVariant, ServicePackage
from .paystack import PaystackAPI
from .tasks import process_webhook_payment
from .utils import process_order_commissions, release_item_escrow, create_service_escrow, release_service_escrow

# --- 1. SHOPPING CART VIEWS (Products Only) ---

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
        
    return redirect('orders:cart')

@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(customer=request.user)
    return render(request, 'cart.html', {'cart': cart})

@login_required
def remove_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    item.delete()
    return redirect('orders:cart')

@login_required
def clear_cart(request):
    cart = Cart.objects.filter(customer=request.user).first()
    if cart:
        cart.items.all().delete()
    return redirect('orders:cart')

@login_required
def increase_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    available_stock = item.variant.stock if item.variant else item.product.stock_count
    
    if item.quantity < available_stock:
        item.quantity += 1
        item.save()
    else:
        messages.error(request, "Maximum available stock reached.")
    return redirect('orders:cart')

@login_required
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete()
    return redirect('orders:cart')


# --- 2. SERVICE BOOKING ENGINE ---

@login_required
def process_service_booking(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        preferred_date = request.POST.get('preferred_date')
        preferred_time = request.POST.get('preferred_time')
        service_location = request.POST.get('service_location')
        customer_notes = request.POST.get('customer_notes', '')

        agreed_price = service.base_price or 0.00
        selected_package = None

        if service.pricing_type == 'PACKAGES':
            package_id = request.POST.get('selected_package')
            if not package_id:
                messages.error(request, "Please select a service package.")
                return redirect('dashboard:service_detail', slug=service.slug)
            
            selected_package = get_object_or_404(ServicePackage, id=package_id)
            agreed_price = selected_package.price

        elif service.pricing_type == 'QUOTE':
            agreed_price = 0.00

        service_order = ServiceOrder.objects.create(
            customer=request.user,
            provider=service.provider,
            service=service,
            package=selected_package,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            service_location=service_location,
            customer_notes=customer_notes,
            agreed_price=agreed_price,
            status=ServiceOrder.ServiceStatus.REQUESTED
        )

        messages.success(request, f"Your request for '{service.name}' has been sent to the provider!")
        return redirect('service_booking_success', reference=service_order.reference_code)
        
    return redirect('dashboard:service_detail', slug=service.slug)

@login_required
def service_booking_success(request, reference):
    service_order = get_object_or_404(ServiceOrder, reference_code=reference, customer=request.user)
    return render(request, 'service_booking_success.html', {'order': service_order})

@login_required
def service_checkout(request, order_id):
    if request.method == 'POST':
        service_order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user, status='ACCEPTED')
        
        paystack = PaystackAPI()
        dynamic_callback = request.build_absolute_uri(reverse('orders:verify_payment'))
        
        metadata = {
            "order_id": service_order.id,
            "type": "service"
        }
        
        response = paystack.initialize_transaction(
            email=request.user.email,
            amount=service_order.agreed_price,
            order_id=service_order.id,
            callback_url=dynamic_callback,
            metadata=metadata
        )
        
        if response.get('status'):
            service_order.paystack_reference = response['data']['reference']
            service_order.save(update_fields=['paystack_reference'])
            return redirect(response['data']['authorization_url'])
        else:
            messages.error(request, "Payment gateway unavailable. Please try again.")
            return redirect('orders:order_history')
    return redirect('orders:order_history')

# --- 3. CHECKOUT & PAYMENT VIEWS (Products Only) ---

@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, customer=request.user)
    
    if not cart.items.exists():
        return redirect('marketplace:home')

    saved_addresses = request.user.addresses.all().order_by('-is_default', '-created_at')

    if request.method == 'GET':
        selected_products = request.GET.getlist('selected_products')
        
        if not selected_products:
            messages.error(request, "Please select at least one item to checkout.")
            return redirect('orders:cart')

        checkout_items = cart.items.filter(id__in=selected_products)
        total = sum(item.get_total for item in checkout_items)
        
        context = {
            'checkout_items': checkout_items,
            'checkout_total': total,
            'selected_products': selected_products, 
            'saved_addresses': saved_addresses,
        }
        return render(request, 'checkout.html', context)

    if request.method == 'POST':
        selected_products = request.POST.getlist('selected_products')
        checkout_items = cart.items.filter(id__in=selected_products)
        
        for item in checkout_items:
            available_stock = item.variant.stock if item.variant else item.product.stock_count
            if item.quantity > available_stock:
                messages.error(request, f"Sorry, {item.product.name} just sold out. Please adjust your quantity.")
                return redirect('orders:cart')

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

        order.total_amount = total_amount
        order.save()

        paystack = PaystackAPI()
        dynamic_callback = request.build_absolute_uri(reverse('orders:verify_payment'))
        
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
            return redirect('orders:cart')

@login_required
def verify_payment(request):
    reference = request.GET.get('reference')
    if not reference:
        return redirect('orders:cart')

    paystack = PaystackAPI()
    response = paystack.verify_transaction(reference)

    if response.get('data') and response['data']['status'] == 'success':
        metadata = response['data'].get('metadata', {})
        order_type = metadata.get('type', 'product')
        order_id = metadata.get('order_id')
        
        if order_type == 'service':
            service_order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user)
            if service_order.status == 'ACCEPTED':
                service_order.status = 'PAID'
                service_order.is_paid = True
                service_order.save(update_fields=['status', 'is_paid'])
                
                create_service_escrow(service_order)
                
                messages.success(request, f"Payment successful! Your booking for {service_order.service.name} is confirmed.")
            return redirect('orders:order_history')
            
        else:
            order = get_object_or_404(Order, id=order_id, customer=request.user)
            PaymentAttempt.objects.filter(reference=reference).update(status='successful')
            
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
    
    PaymentAttempt.objects.filter(reference=reference).update(status='failed')
    return redirect('orders:cart')

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


# --- 4. CUSTOMER DASHBOARD VIEWS ---

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_success.html', {'order': order})

@login_required
def order_history(request):
    if request.user.role == 'PROVIDER':
        # FIXED: Added namespace to prevent NoReverseMatch crash
        return redirect('dashboard:provider_dashboard')
        
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    service_bookings = ServiceOrder.objects.filter(customer=request.user).order_by('-created_at')
    
    return render(request, 'order_history.html', {
        'orders': orders,
        'service_bookings': service_bookings
    })

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
            
            all_completed = not item.order.items.exclude(status='COMPLETED').exists()
            if all_completed:
                item.order.status = 'completed'
                item.order.save(update_fields=['status'])
                
            release_item_escrow(item)
            messages.success(request, f"Delivery confirmed for {item.product.name}! The vendor has been credited.")
        else:
            messages.error(request, "Invalid delivery code. Please check the code provided for this item.")
            
    return redirect('order_details', order_id=item.order.id)

@login_required
def customer_confirm_service(request, order_id):
    if request.method == 'POST':
        service_order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user, status='COMPLETED')
        
        service_order.status = 'CONFIRMED'
        service_order.save(update_fields=['status'])
        
        release_service_escrow(service_order)
        
        messages.success(request, f"You confirmed the completion of {service_order.service.name}. The provider has been paid!")
    return redirect('orders:order_history')

@login_required
def reject_quote(request, order_id):
    if request.method == 'POST':
        # Ensure the user actually owns this order
        order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user, status='QUOTE_SENT')
        
        # Update the parent order
        order.status = 'DECLINED'
        order.save(update_fields=['status'])
        
        # Update the quote status
        if hasattr(order, 'quote'):
            order.quote.status = 'REJECTED'
            order.quote.save(update_fields=['status'])
            
        messages.info(request, f"You rejected the quote for {order.service.name}.")
        
    return redirect('orders:order_history')

@login_required
def send_order_message(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(ServiceOrder, id=order_id)
        
        # Security: Ensure the user is either the customer who booked it, or the provider assigned to it
        is_customer = request.user == order.customer
        is_provider = hasattr(request.user, 'provider_profile') and request.user.provider_profile == order.provider
        
        if not (is_customer or is_provider):
            return HttpResponseForbidden("You are not authorized to send messages for this order.")
            
        body = request.POST.get('body', '').strip()
        attachment = request.FILES.get('attachment')
        
        if body or attachment:
            OrderMessage.objects.create(
                order=order,
                sender=request.user,
                body=body,
                attachment=attachment
            )
            
        # Redirect the user back to the exact page they sent the message from (either dashboard or order history)
        return redirect(request.META.get('HTTP_REFERER', 'marketplace:home'))

@login_required
def order_chat(request, order_id):
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    # Security: Ensure only the customer or the assigned provider can see this chat
    is_customer = request.user == order.customer
    is_provider = hasattr(request.user, 'provider_profile') and request.user.provider_profile == order.provider
    
    if not (is_customer or is_provider):
        return HttpResponseForbidden("You are not authorized to view this conversation.")
        
    # Mark messages from the other person as read when they open the page
    unread_messages = order.messages.exclude(sender=request.user).filter(is_read=False)
    unread_messages.update(is_read=True)
    
    # Determine who the user is talking to for the header
    chat_partner = order.provider.business_name if is_customer else order.customer.get_full_name() or order.customer.username
        
    context = {
        'order': order,
        'chat_messages': order.messages.all(),
        'is_customer': is_customer,
        'chat_partner': chat_partner
    }
    return render(request, 'order_chat.html', context)

@login_required
def report_dispute(request, order_id):
    # Ensure the user owns this order and it hasn't been closed/confirmed yet
    order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user)
    
    if order.status in ['CONFIRMED', 'CANCELLED', 'DECLINED']:
        messages.error(request, "This order cannot be disputed at this time.")
        return redirect('orders:order_history')

    # If they already submitted a dispute, don't let them submit another one
    if hasattr(order, 'dispute'):
        messages.info(request, "You have already filed a dispute for this order. Our team is reviewing it.")
        return redirect('orders:order_history')

    if request.method == 'POST':
        reason = request.POST.get('reason')
        description = request.POST.get('description')
        evidence = request.FILES.get('evidence')

        if not description:
            messages.error(request, "Please provide a description of the problem.")
            return redirect('orders:report_dispute', order_id=order.id)

        try:
            with transaction.atomic():
                # Create the dispute record
                ServiceDispute.objects.create(
                    order=order,
                    reason=reason,
                    description=description,
                    evidence=evidence
                )
                
                # Freeze the order
                order.status = 'DISPUTED'
                order.save(update_fields=['status'])

            messages.success(request, "Your dispute has been submitted. Our team will review the evidence and contact you shortly.")
            return redirect('orders:order_history')
            
        except Exception as e:
            messages.error(request, f"Error submitting dispute: {str(e)}")

    return render(request, 'report_dispute.html', {'order': order, 'reasons': ServiceDispute.DisputeReason.choices})