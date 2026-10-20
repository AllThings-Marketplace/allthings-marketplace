import hmac
import hashlib
import json
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db.models import F, Q, Sum
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import (
    Order, OrderItem, ShippingAddress, Cart, CartItem, 
    PaymentAttempt, ServiceOrder, OrderMessage, ServiceDispute,
    SupportTicket, TicketMessage
)
from marketplace.models import Product, Service, ProductVariant, ServicePackage, UserInteraction
from .paystack import PaystackAPI
from .tasks import process_webhook_payment
from .utils import process_order_commissions, release_item_escrow, create_service_escrow, release_service_escrow
from .logistics import LogisticsEngine, normalize_location


# --- UNIVERSAL NOTIFICATION DISPATCHER ---

def _notify(recipient, title, message, target_obj=None, notif_type='ORDER'):
    """
    Creates an in-app Bell Notification linked via GenericForeignKey.
    Because notifications/signals.py listens to post_save on Notification,
    this automatically queues the Celery HTML email task as well.
    """
    if not recipient:
        return
    try:
        from notifications.models import Notification
        ct = ContentType.objects.get_for_model(target_obj) if target_obj else None
        obj_id = target_obj.id if target_obj else None

        Notification.objects.create(
            recipient=recipient,
            notification_type=notif_type,
            title=title,
            message=message,
            content_type=ct,
            object_id=obj_id
        )
    except Exception:
        # Never allow a notification error to interrupt a financial or order transaction
        pass


def _notify_order_paid(order):
    """Notifies the customer and every unique vendor whose items were purchased."""
    _notify(
        recipient=order.customer,
        title=f"Order Confirmed ({order.reference})",
        message=f"Your payment of NGN {order.total_amount:,.2f} was received and is safely held in escrow.",
        target_obj=order,
        notif_type='ORDER'
    )
    notified_providers = set()
    for item in order.items.select_related('product__provider__user').all():
        if item.product and item.product.provider and item.product.provider.user:
            provider_user = item.product.provider.user
            if provider_user.id not in notified_providers:
                notified_providers.add(provider_user.id)
                _notify(
                    recipient=provider_user,
                    title=f"New Product Order ({order.reference})",
                    message=f"You have new paid item(s) ready for fulfillment on Order {order.reference}.",
                    target_obj=order,
                    notif_type='ORDER'
                )


# --- 1. SHOPPING CART VIEWS (Products Only) ---

def _get_cart_metrics(cart):
    """Returns total unit quantity, unique line items, and subtotal for live UI updates."""
    if not cart:
        return {'cart_count': 0, 'unique_items': 0, 'cart_total': 0.0}
    total_units = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
    unique_items = cart.items.count()
    return {
        'cart_count': total_units,
        'unique_items': unique_items,
        'cart_total': float(cart.get_cart_total),
    }


def _is_ajax(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    
    variant = None
    qty_to_add = 1

    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
        try:
            qty_to_add = max(1, int(request.POST.get('quantity', 1)))
        except (ValueError, TypeError):
            qty_to_add = 1

    cart_item, _ = CartItem.objects.get_or_create(
        cart=cart, 
        product=product,
        variant=variant,
        defaults={'quantity': 0}
    )
    
    available_stock = variant.stock if variant else product.stock_count
    
    if available_stock <= 0:
        msg = f"Sorry, {product.name} is currently out of stock."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'message': msg, **_get_cart_metrics(cart)}, status=400)
        messages.error(request, msg)
        return redirect(request.META.get('HTTP_REFERER', 'orders:cart'))

    if (cart_item.quantity + qty_to_add) <= available_stock:
        cart_item.quantity += qty_to_add
        cart_item.save()
        
        # Log High-Intent CART Signal (Weight = 8)
        UserInteraction.objects.create(
            user=request.user,
            content_type=ContentType.objects.get_for_model(Product),
            object_id=product.id,
            interaction_type=UserInteraction.InteractionType.CART,
            weight=8
        )
        
        msg = f"{product.name} added to cart!"
        if _is_ajax(request):
            return JsonResponse({
                'status': 'success',
                'message': msg,
                'item_quantity': cart_item.quantity,
                'item_total': float(cart_item.get_total),
                **_get_cart_metrics(cart)
            })
        
        messages.success(request, msg)
    else:
        msg = f"Cannot add more. Only {available_stock} in stock."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'message': msg, **_get_cart_metrics(cart)}, status=400)
        messages.error(request, msg)
        
    return redirect('orders:cart')


@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return render(request, 'orders/cart.html', {'cart': cart})


@login_required
def remove_item(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    cart = item.cart
    item.delete()
    if _is_ajax(request):
        return JsonResponse({'status': 'success', **_get_cart_metrics(cart)})
    return redirect('orders:cart')


@login_required
def clear_cart(request):
    cart = Cart.objects.filter(customer=request.user).first()
    if cart:
        cart.items.all().delete()
    if _is_ajax(request):
        return JsonResponse({'status': 'success', **_get_cart_metrics(cart)})
    return redirect('orders:cart')


@login_required
def increase_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    available_stock = item.variant.stock if item.variant else item.product.stock_count
    
    if item.quantity < available_stock:
        item.quantity += 1
        item.save()
        if _is_ajax(request):
            return JsonResponse({
                'status': 'success',
                'item_quantity': item.quantity,
                'item_total': float(item.get_total),
                **_get_cart_metrics(item.cart)
            })
    else:
        msg = "Maximum available stock reached."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'message': msg, **_get_cart_metrics(item.cart)}, status=400)
        messages.error(request, msg)
    return redirect('orders:cart')


@login_required
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    cart = item.cart
    if item.quantity > 1:
        item.quantity -= 1
        item.save()
        if _is_ajax(request):
            return JsonResponse({
                'status': 'success',
                'item_quantity': item.quantity,
                'item_total': float(item.get_total),
                **_get_cart_metrics(cart)
            })
    else:
        item.delete()
        if _is_ajax(request):
            return JsonResponse({
                'status': 'success',
                'item_quantity': 0,
                'item_total': 0.0,
                **_get_cart_metrics(cart)
            })
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
                return redirect('marketplace:service_detail', slug=service.slug)
            
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
        return redirect('orders:service_booking_success', reference=service_order.reference_code)
        
    return redirect('marketplace:service_detail', slug=service.slug)


@login_required
def service_booking_success(request, reference):
    service_order = get_object_or_404(ServiceOrder, reference_code=reference, customer=request.user)
    return render(request, 'orders/service_booking_success.html', {'order': service_order})


@login_required
def service_checkout(request, order_id):
    if request.method == 'POST':
        service_order = get_object_or_404(
            ServiceOrder,
            id=order_id,
            customer=request.user,
            status__in=['ACCEPTED', 'QUOTE_SENT']
        )

        if service_order.status == 'QUOTE_SENT':
            service_order.status = 'ACCEPTED'
            if hasattr(service_order, 'quote'):
                service_order.quote.status = 'ACCEPTED'
                service_order.quote.save(update_fields=['status'])
                service_order.agreed_price = service_order.quote.total_amount
            service_order.save(update_fields=['status', 'agreed_price'])
        
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


# --- 3. CHECKOUT, LIVE SHIPPING QUOTES & PAYMENT VIEWS (Products Only) ---

@login_required
def get_shipping_quotes_ajax(request):
    """
    AJAX endpoint called whenever the customer switches their saved address
    or changes the State / City fields on the checkout page.
    Returns live, cryptographically signed courier quotes for all vendor shipments.
    """
    cart = Cart.objects.filter(customer=request.user).first()
    if not cart:
        return JsonResponse({'status': 'error', 'message': 'Cart is empty.'}, status=400)

    selected_products = request.GET.getlist('selected_products[]') or request.GET.getlist('selected_products')
    checkout_items = cart.items.filter(id__in=selected_products).select_related('product__provider', 'variant')

    if not checkout_items.exists():
        return JsonResponse({'status': 'error', 'message': 'No items selected.'}, status=400)

    address_id = request.GET.get('address_id', 'new')
    dest_state = request.GET.get('region', 'Rivers State').strip()
    dest_city = request.GET.get('city', '').strip()

    if address_id and address_id != 'new':
        saved_addr = ShippingAddress.objects.filter(id=address_id, user=request.user).first()
        if saved_addr:
            dest_state = saved_addr.region or 'Rivers State'
            dest_city = saved_addr.city or ''

    quote_data = LogisticsEngine.get_quotes_for_checkout(
        cart_items=checkout_items,
        dest_state=dest_state,
        dest_city=dest_city
    )

    subtotal = sum(item.get_total for item in checkout_items)

    return JsonResponse({
        'status': 'success',
        'subtotal': float(subtotal),
        'dest_state': dest_state,
        'dest_city': dest_city,
        'vendor_count': quote_data.get('vendor_count', 1),
        'shipment_groups': quote_data.get('shipment_groups', []),
        'quotes': quote_data.get('quotes', []),
    })


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

        checkout_items = cart.items.filter(id__in=selected_products).select_related('product__provider', 'variant')
        if not checkout_items.exists():
            messages.error(request, "Selected items are no longer in your cart.")
            return redirect('orders:cart')

        subtotal = sum(item.get_total for item in checkout_items)

        default_addr = saved_addresses.first()
        initial_state = default_addr.region if default_addr else 'Rivers State'
        initial_city = (default_addr.city or '') if default_addr else 'Port Harcourt'

        quote_data = LogisticsEngine.get_quotes_for_checkout(
            cart_items=checkout_items,
            dest_state=initial_state,
            dest_city=initial_city
        )
        quotes = quote_data.get('quotes', [])
        default_quote = quotes[0] if quotes else None
        initial_shipping = Decimal(str(default_quote['amount'])) if default_quote else Decimal('0.00')
        
        context = {
            'checkout_items': checkout_items,
            'checkout_subtotal': subtotal,
            'initial_shipping': initial_shipping,
            'checkout_total': subtotal + initial_shipping,
            'selected_products': selected_products, 
            'saved_addresses': saved_addresses,
            'quotes': quotes,
            'shipment_groups': quote_data.get('shipment_groups', []),
            'vendor_count': quote_data.get('vendor_count', 1),
        }
        return render(request, 'orders/checkout.html', context)

    if request.method == 'POST':
        selected_products = request.POST.getlist('selected_products')
        checkout_items = list(
            cart.items.filter(id__in=selected_products).select_related('product__provider', 'variant')
        )

        if not checkout_items:
            messages.error(request, "No valid items found for checkout.")
            return redirect('orders:cart')
        
        for item in checkout_items:
            available_stock = item.variant.stock if item.variant else item.product.stock_count
            if item.quantity > available_stock:
                messages.error(request, f"Sorry, {item.product.name} just sold out. Please adjust your quantity.")
                return redirect('orders:cart')

        # 1. Resolve Customer Delivery Address
        selected_address_id = request.POST.get('selected_address')
        if selected_address_id and selected_address_id != 'new':
            address = get_object_or_404(ShippingAddress, id=selected_address_id, user=request.user)
            first_name = address.first_name
            last_name = address.last_name
            phone = address.phone
            alt_phone = address.alt_phone
            whatsapp = address.whatsapp
            region = address.region
            city = address.city or ''
            street_address = address.street_address
            landmark = address.landmark or ''
        else:
            label = request.POST.get('address_label', 'Home').strip() or 'Home'
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone = request.POST.get('phone', '').strip()
            alt_phone = request.POST.get('alt_phone', '').strip()
            whatsapp = request.POST.get('whatsapp', '').strip()
            region = request.POST.get('region', '').strip()
            city = request.POST.get('city', '').strip()
            street_address = request.POST.get('street_address', '').strip()
            landmark = request.POST.get('landmark', '').strip()
            save_for_future = request.POST.get('save_address') == 'on'

            if not (first_name and last_name and phone and region and street_address):
                messages.error(request, "Please fill in all required delivery address fields.")
                return redirect('orders:cart')
            
            if save_for_future or not saved_addresses.exists():
                ShippingAddress.objects.create(
                    user=request.user,
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
                    is_default=not saved_addresses.exists()
                )

        # 2. Verify Signed Shipping Quote (or Recalculate on Backend if Stale/Mismatched)
        submitted_token = request.POST.get('quote_token', '')
        submitted_courier = request.POST.get('selected_courier', 'GIGL')
        verified_quote = LogisticsEngine.verify_quote_token(submitted_token)

        if (
            not verified_quote
            or verified_quote.get('dest_state') != normalize_location(region)
            or verified_quote.get('dest_city') != normalize_location(city)
        ):
            fresh_data = LogisticsEngine.get_quotes_for_checkout(checkout_items, region, city)
            fresh_quotes = fresh_data.get('quotes', [])
            matched = next((q for q in fresh_quotes if q['courier_code'] == submitted_courier), None)
            if not matched and fresh_quotes:
                matched = fresh_quotes[0]

            if matched:
                shipping_fee = Decimal(str(matched['amount']))
                selected_courier = matched['courier_code']
                leg_fees = {leg['provider_id']: Decimal(str(leg['fee'])) for leg in matched.get('legs', [])}
            else:
                shipping_fee = Decimal('2500.00')
                selected_courier = 'GIGL'
                leg_fees = {}
        else:
            shipping_fee = Decimal(str(verified_quote['total_fee']))
            selected_courier = verified_quote['courier_code']
            leg_fees = {leg['provider_id']: Decimal(str(leg['fee'])) for leg in verified_quote.get('legs', [])}

        # 3. Create Order & Immutable Snapshots Inside an Atomic Transaction
        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                status='unpaid',
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                alt_phone=alt_phone,
                whatsapp=whatsapp,
                region=region,
                city=city,
                street_address=street_address,
                landmark=landmark,
                selected_courier=selected_courier,
            )

            subtotal = Decimal('0.00')
            allocated_providers = set()

            for c_item in checkout_items:
                price = c_item.variant.price_override if c_item.variant and c_item.variant.price_override else c_item.product.price
                provider_id = c_item.product.provider_id if c_item.product else 0

                item_shipping_fee = Decimal('0.00')
                if provider_id not in allocated_providers and provider_id in leg_fees:
                    item_shipping_fee = leg_fees[provider_id]
                    allocated_providers.add(provider_id)

                OrderItem.objects.create(
                    order=order,
                    product=c_item.product,
                    variant=c_item.variant,
                    quantity=c_item.quantity,
                    price=price,
                    shipping_fee=item_shipping_fee,
                    logistics_provider=selected_courier,
                    status='PENDING'
                )
                subtotal += (price * c_item.quantity)
                c_item.delete()

            order.subtotal = subtotal
            order.shipping_fee = shipping_fee
            order.total_amount = subtotal + shipping_fee
            order.save(update_fields=['subtotal', 'shipping_fee', 'total_amount'])

        # 4. Initialize Paystack Payment for (Subtotal + Shipping Fee)
        paystack = PaystackAPI()
        dynamic_callback = request.build_absolute_uri(reverse('orders:verify_payment'))
        metadata = {
            "order_id": order.id,
            "type": "product"
        }
        
        response = paystack.initialize_transaction(
            email=request.user.email,
            amount=order.total_amount,
            order_id=order.id,
            callback_url=dynamic_callback,
            metadata=metadata
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
            messages.error(request, "Payment gateway unavailable. You can retry payment from your Order Details page.")
            return redirect('orders:order_details', order_id=order.id)


@login_required
def verify_payment(request):
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "Payment was cancelled or no reference was provided.")
        return redirect('orders:order_history')

    paystack = PaystackAPI()
    response = paystack.verify_transaction(reference)

    if response.get('data'):
        metadata = response['data'].get('metadata', {})
        order_type = metadata.get('type', 'product')
        order_id = metadata.get('order_id')
        
        # --- SUCCESSFUL PAYMENT ---
        if response['data']['status'] == 'success':
            if order_type == 'service':
                service_order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user)
                if service_order.status == 'ACCEPTED':
                    service_order.status = 'PAID'
                    service_order.is_paid = True
                    service_order.save(update_fields=['status', 'is_paid'])
                    
                    if service_order.service:
                        UserInteraction.objects.create(
                            user=request.user,
                            content_type=ContentType.objects.get_for_model(Service),
                            object_id=service_order.service.id,
                            interaction_type=UserInteraction.InteractionType.PURCHASE,
                            weight=15
                        )
                    
                    create_service_escrow(service_order)

                    service_name = service_order.service.name if service_order.service else service_order.reference_code
                    if service_order.provider and service_order.provider.user:
                        _notify(
                            recipient=service_order.provider.user,
                            title=f"Service Booking Paid ({service_order.reference_code})",
                            message=f"{request.user.username} paid NGN {service_order.agreed_price:,.2f} into escrow for '{service_name}'.",
                            target_obj=service_order,
                            notif_type='ORDER'
                        )
                    _notify(
                        recipient=request.user,
                        title=f"Service Payment Confirmed ({service_order.reference_code})",
                        message=f"Your payment for '{service_name}' is secured in escrow.",
                        target_obj=service_order,
                        notif_type='ORDER'
                    )

                    messages.success(request, f"Payment successful! Your booking for {service_name} is confirmed.")
                return redirect('orders:order_history')
                
            else:
                order = get_object_or_404(Order, id=order_id, customer=request.user)
                PaymentAttempt.objects.filter(reference=reference).update(status='successful')
                
                if order.status == 'unpaid':
                    order.status = 'confirmed'
                    order.save(update_fields=['status'])
                    
                    product_ct = ContentType.objects.get_for_model(Product)
                    
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
                            
                            UserInteraction.objects.create(
                                user=order.customer,
                                content_type=product_ct,
                                object_id=item.product.id,
                                interaction_type=UserInteraction.InteractionType.PURCHASE,
                                weight=15
                            )
                    
                    process_order_commissions(order)
                    _notify_order_paid(order)

                return redirect('orders:order_success', order_id=order.id)
        
        # --- CANCELLED OR FAILED PAYMENT ---
        else:
            if order_type == 'service':
                messages.error(request, "Service payment was cancelled or failed. Please try again.")
                return redirect('orders:order_history')
            else:
                PaymentAttempt.objects.filter(reference=reference).update(status='failed')
                messages.error(request, "Payment was cancelled or failed. You can retry the payment below.")
                return redirect('orders:order_details', order_id=order_id)
    
    # --- API FAILURE FALLBACK ---
    PaymentAttempt.objects.filter(reference=reference).update(status='failed')
    messages.error(request, "We could not verify the payment status with our provider. If you were debited, please use our Instant Payment Recovery tool.")
    return redirect('orders:support_center')


@csrf_exempt
def paystack_webhook(request):
    if request.method == 'POST':
        payload = request.body
        sig_header = request.headers.get('x-paystack-signature')
        secret_key = settings.PAYSTACK_SECRET_KEY.encode('utf-8')

        hash_val = hmac.new(secret_key, payload, hashlib.sha512).hexdigest()
        if hash_val != sig_header:
            return HttpResponse(status=400)

        event_data = json.loads(payload)
        
        if event_data.get('event') == 'charge.success':
            metadata = event_data['data'].get('metadata', {})
            order_id = metadata.get('order_id')
            
            if order_id:
                process_webhook_payment.delay(order_id, event_data['data']['reference'])

        return HttpResponse(status=200)
    return HttpResponse(status=405)


@login_required
def retry_payment(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, customer=request.user, status='unpaid')
        
        paystack = PaystackAPI()
        dynamic_callback = request.build_absolute_uri(reverse('orders:verify_payment'))
        
        metadata = {
            "order_id": order.id,
            "type": "product"
        }
        
        response = paystack.initialize_transaction(
            email=request.user.email,
            amount=order.total_amount,
            order_id=order.id,
            callback_url=dynamic_callback,
            metadata=metadata
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
            return redirect('orders:order_details', order_id=order.id)
            
    return redirect('orders:order_details', order_id=order_id)


# --- 4. CUSTOMER DASHBOARD VIEWS ---

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_history(request):
    if request.user.role == 'PROVIDER':
        return redirect('dashboard:provider_dashboard')
        
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    service_bookings = ServiceOrder.objects.filter(customer=request.user).order_by('-created_at')
    
    return render(request, 'orders/order_history.html', {
        'orders': orders,
        'service_bookings': service_bookings
    })


@login_required
def order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'orders/order_details.html', {'order': order})


@login_required
def confirm_item_delivery(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)
        submitted_code = request.POST.get('delivery_code', '').strip()
        
        if item.status == 'COMPLETED':
            messages.info(request, "This item has already been marked as completed.")
            return redirect('orders:order_details', order_id=item.order.id)
        if item.status in ['DISPUTED', 'REFUNDED', 'CANCELLED']:
            messages.error(request, f"This item is currently {item.get_status_display()} and cannot be confirmed via PIN.")
            return redirect('orders:order_details', order_id=item.order.id)
            
        if submitted_code == item.delivery_code:
            with transaction.atomic():
                item.status = 'COMPLETED'
                item.save(update_fields=['status'])
                
                all_completed = not item.order.items.exclude(status='COMPLETED').exists()
                if all_completed:
                    item.order.status = 'completed'
                    item.order.save(update_fields=['status'])
                    
                release_item_escrow(item)

            if item.product and item.product.provider and item.product.provider.user:
                _notify(
                    recipient=item.product.provider.user,
                    title=f"Escrow Released: {item.product.name}",
                    message=f"Customer confirmed delivery for '{item.product.name}' ({item.order.reference}). Funds have been credited to your wallet!",
                    target_obj=item.order,
                    notif_type='ORDER'
                )

            messages.success(request, f"Delivery confirmed for {item.product.name}! The vendor has been credited.")
        else:
            messages.error(request, "Invalid delivery code. Please check the code provided for this item.")
            
    return redirect('orders:order_details', order_id=item.order.id)


@login_required
def customer_confirm_service(request, order_id):
    if request.method == 'POST':
        service_order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user, status='COMPLETED')
        
        with transaction.atomic():
            service_order.status = 'CONFIRMED'
            service_order.save(update_fields=['status'])
            release_service_escrow(service_order)
        
        service_name = service_order.service.name if service_order.service else service_order.reference_code
        if service_order.provider and service_order.provider.user:
            _notify(
                recipient=service_order.provider.user,
                title=f"Service Escrow Released ({service_order.reference_code})",
                message=f"{request.user.username} confirmed completion of '{service_name}'. Your payout has been credited to your wallet!",
                target_obj=service_order,
                notif_type='ORDER'
            )

        messages.success(request, f"You confirmed the completion of {service_name}. The provider has been paid!")
    return redirect('orders:order_history')


@login_required
def reject_quote(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user, status='QUOTE_SENT')
        
        order.status = 'DECLINED'
        order.save(update_fields=['status'])
        
        if hasattr(order, 'quote'):
            order.quote.status = 'REJECTED'
            order.quote.save(update_fields=['status'])
            
        service_name = order.service.name if order.service else order.reference_code
        if order.provider and order.provider.user:
            _notify(
                recipient=order.provider.user,
                title=f"Quote Declined ({order.reference_code})",
                message=f"The customer declined the quote for '{service_name}'.",
                target_obj=order,
                notif_type='ORDER'
            )

        messages.info(request, f"You rejected the quote for {service_name}.")
        
    return redirect('orders:order_history')


@login_required
def send_order_message(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(ServiceOrder, id=order_id)
        
        is_customer = request.user == order.customer
        is_provider = hasattr(request.user, 'provider_profile') and request.user.provider_profile == order.provider
        
        if not (is_customer or is_provider):
            return HttpResponseForbidden("You are not authorized to send messages for this order.")
            
        body = request.POST.get('body', '').strip()
        attachment = request.FILES.get('attachment')
        
        if body or attachment:
            message = OrderMessage.objects.create(
                order=order,
                sender=request.user,
                body=body,
                attachment=attachment
            )
            
            recipient = order.provider.user if is_customer else order.customer
            snippet = (body[:60] + '...') if len(body) > 60 else (body or 'Sent an attachment')
            _notify(
                recipient=recipient,
                title=f"New Message on {order.reference_code}",
                message=f"{request.user.username}: \"{snippet}\"",
                target_obj=order,
                notif_type='MESSAGE'
            )
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'body': message.body,
                    'attachment_url': message.attachment.url if message.attachment else None,
                    'time': timezone.localtime(message.created_at).strftime("%I:%M %p")
                })
                
        return redirect(request.META.get('HTTP_REFERER', 'marketplace:home'))


@login_required
def order_chat(request, order_id):
    order = get_object_or_404(ServiceOrder, id=order_id)
    
    is_customer = request.user == order.customer
    is_provider = hasattr(request.user, 'provider_profile') and request.user.provider_profile == order.provider
    
    if not (is_customer or is_provider):
        return HttpResponseForbidden("You are not authorized to view this conversation.")
        
    unread_messages = order.messages.exclude(sender=request.user).filter(is_read=False)
    unread_messages.update(is_read=True)
    
    chat_partner = order.provider.business_name if is_customer else order.customer.get_full_name() or order.customer.username
        
    context = {
        'order': order,
        'chat_messages': order.messages.all(),
        'is_customer': is_customer,
        'chat_partner': chat_partner
    }
    return render(request, 'orders/order_chat.html', context)


@login_required
def report_dispute(request, order_id):
    order = get_object_or_404(ServiceOrder, id=order_id, customer=request.user)
    
    if order.status in ['CONFIRMED', 'CANCELLED', 'DECLINED']:
        messages.error(request, "This order cannot be disputed at this time.")
        return redirect('orders:order_history')

    if hasattr(order, 'dispute'):
        existing_tkt = SupportTicket.objects.filter(service_order=order).first()
        if existing_tkt:
            return redirect('orders:ticket_detail', reference=existing_tkt.ticket_reference)
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
                dispute = ServiceDispute.objects.create(
                    order=order,
                    reason=reason,
                    description=description,
                    evidence=evidence
                )
                
                order.status = 'DISPUTED'
                order.save(update_fields=['status'])

                shared_evidence = dispute.evidence.name if dispute.evidence else None

                ticket = SupportTicket.objects.create(
                    user=request.user,
                    category=SupportTicket.Category.SERVICE_DISPUTE,
                    priority=SupportTicket.Priority.URGENT,
                    service_order=order,
                    subject=f"Service Dispute ({dispute.get_reason_display()}): {order.reference_code}",
                    description=description,
                    evidence=shared_evidence
                )
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    body=description,
                    attachment=shared_evidence,
                    is_staff_reply=False
                )

            if order.provider and order.provider.user:
                _notify(
                    recipient=order.provider.user,
                    title=f"Escrow Frozen: Service Dispute ({ticket.ticket_reference})",
                    message=f"The customer filed a dispute on booking {order.reference_code} ({dispute.get_reason_display()}). Please respond in the ticket thread.",
                    target_obj=ticket,
                    notif_type='ORDER'
                )

            messages.success(request, f"Dispute Ticket {ticket.ticket_reference} opened. Escrow is now frozen while our team reviews your evidence.")
            return redirect('orders:ticket_detail', reference=ticket.ticket_reference)
            
        except Exception as e:
            messages.error(request, f"Error submitting dispute: {str(e)}")

    return render(request, 'orders/report_dispute.html', {'order': order, 'reasons': ServiceDispute.DisputeReason.choices})


# --- 5. UNIFIED CUSTOMER SUPPORT, SELF-SERVICE TRIAGE & ESCROW FREEZE ---

@login_required
def support_center(request):
    """
    Main Help & Support hub:
    1. Displays unverified PaymentAttempts for 1-click self-service Paystack re-verification.
    2. Allows users and providers to open contextual support tickets.
    3. Lists all active and past support tickets.
    """
    if request.method == 'POST':
        category = request.POST.get('category', SupportTicket.Category.GENERAL)
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')
        
        order_id = request.POST.get('order_id')
        order_item_id = request.POST.get('order_item_id')
        service_order_id = request.POST.get('service_order_id')

        if not subject or not description:
            messages.error(request, "Please provide both a subject and a detailed description.")
            return redirect('orders:support_center')

        involved_provider_user = None

        with transaction.atomic():
            ticket = SupportTicket(
                user=request.user,
                category=category,
                subject=subject,
                description=description,
                evidence=evidence
            )

            if order_item_id:
                item = OrderItem.objects.filter(id=order_item_id, order__customer=request.user).first()
                if item:
                    ticket.order_item = item
                    ticket.order = item.order
                    if item.product and item.product.provider:
                        involved_provider_user = item.product.provider.user
                    if category == SupportTicket.Category.PRODUCT_DISPUTE and item.status not in ['COMPLETED', 'REFUNDED', 'CANCELLED']:
                        item.status = 'DISPUTED'
                        item.save(update_fields=['status'])

            elif order_id:
                order = Order.objects.filter(id=order_id, customer=request.user).first()
                if order:
                    ticket.order = order

            if service_order_id:
                s_order = ServiceOrder.objects.filter(
                    Q(id=service_order_id) & (Q(customer=request.user) | Q(provider__user=request.user))
                ).first()
                if s_order:
                    ticket.service_order = s_order
                    if s_order.provider and s_order.provider.user != request.user:
                        involved_provider_user = s_order.provider.user
                    if category == SupportTicket.Category.SERVICE_DISPUTE and s_order.status not in ['CONFIRMED', 'CANCELLED', 'DECLINED']:
                        s_order.status = 'DISPUTED'
                        s_order.save(update_fields=['status'])

            ticket.save()

            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=description,
                attachment=ticket.evidence.name if ticket.evidence else None,
                is_staff_reply=False
            )

        _notify(
            recipient=request.user,
            title=f"Support Ticket Opened ({ticket.ticket_reference})",
            message=f"We received your ticket '{ticket.subject}'. Our team will respond shortly.",
            target_obj=ticket,
            notif_type='SYSTEM'
        )

        if involved_provider_user and involved_provider_user != request.user:
            _notify(
                recipient=involved_provider_user,
                title=f"Escrow Dispute Opened ({ticket.ticket_reference})",
                message=f"A customer opened a support ticket regarding '{ticket.subject}'. Click to view details and respond.",
                target_obj=ticket,
                notif_type='ORDER'
            )

        messages.success(request, f"Support Ticket {ticket.ticket_reference} created! Our team is reviewing your request.")
        return redirect('orders:ticket_detail', reference=ticket.ticket_reference)

    if hasattr(request.user, 'provider_profile'):
        provider = request.user.provider_profile
        tickets = SupportTicket.objects.filter(
            Q(user=request.user) |
            Q(order_item__product__provider=provider) |
            Q(service_order__provider=provider)
        ).select_related('order', 'order_item__product', 'service_order__service').distinct()
    else:
        tickets = SupportTicket.objects.filter(user=request.user).select_related(
            'order', 'order_item__product', 'service_order__service'
        )

    unverified_attempts = PaymentAttempt.objects.filter(
        order__customer=request.user,
        order__status='unpaid'
    ).exclude(status='successful').select_related('order').order_by('-created_at')[:5]

    disputable_items = OrderItem.objects.filter(
        order__customer=request.user
    ).exclude(status__in=['PENDING', 'COMPLETED', 'REFUNDED', 'CANCELLED']).select_related('product', 'order').order_by('-id')[:15]

    recent_orders = Order.objects.filter(customer=request.user).order_by('-created_at')[:10]
    recent_services = ServiceOrder.objects.filter(
        Q(customer=request.user) | Q(provider__user=request.user)
    ).order_by('-created_at')[:10]

    context = {
        'tickets': tickets,
        'unverified_attempts': unverified_attempts,
        'disputable_items': disputable_items,
        'recent_orders': recent_orders,
        'recent_services': recent_services,
        'categories': SupportTicket.Category.choices,
    }
    return render(request, 'support/support_center.html', context)


@login_required
def reverify_payment_attempt(request, attempt_id):
    """
    1-Click Self-Service Triage: Queries Paystack live for a pending/failed PaymentAttempt.
    If Paystack confirms the debit succeeded, it fulfills the order immediately.
    """
    if request.method != 'POST':
        return redirect('orders:support_center')

    attempt = get_object_or_404(PaymentAttempt, id=attempt_id, order__customer=request.user)
    order = attempt.order

    if order.status != 'unpaid':
        messages.info(request, f"Order {order.reference} is already marked as {order.get_status_display()}.")
        return redirect('orders:order_details', order_id=order.id)

    paystack = PaystackAPI()
    response = paystack.verify_transaction(attempt.reference)

    if response.get('data') and response['data'].get('status') == 'success':
        with transaction.atomic():
            attempt.status = 'successful'
            attempt.resolved_at = timezone.now()
            attempt.save(update_fields=['status', 'resolved_at'])

            if order.status == 'unpaid':
                order.status = 'confirmed'
                order.save(update_fields=['status'])

                product_ct = ContentType.objects.get_for_model(Product)

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

                        UserInteraction.objects.create(
                            user=order.customer,
                            content_type=product_ct,
                            object_id=item.product.id,
                            interaction_type=UserInteraction.InteractionType.PURCHASE,
                            weight=15
                        )

                process_order_commissions(order)
                _notify_order_paid(order)

        messages.success(request, f"Payment verified! Order {order.reference} is now confirmed and in escrow.")
        return redirect('orders:order_details', order_id=order.id)
    else:
        gw_status = response.get('data', {}).get('status', 'unconfirmed')
        messages.warning(
            request,
            f"Paystack currently reports reference {attempt.reference} as '{gw_status}'. "
            f"If your bank account was debited, please submit a Payment Issue ticket below with your debit receipt."
        )
        return redirect('orders:support_center')


@login_required
def report_item_dispute(request, item_id):
    """
    Dedicated physical product dispute view:
    Freezes the 72-hour auto-escrow timer by flipping OrderItem.status to 'DISPUTED'
    and opens an URGENT SupportTicket.
    """
    item = get_object_or_404(OrderItem, id=item_id, order__customer=request.user)

    if item.status in ['COMPLETED', 'CANCELLED', 'REFUNDED']:
        messages.error(request, "This item's escrow has already been finalized and cannot be disputed.")
        return redirect('orders:order_details', order_id=item.order.id)

    existing_ticket = SupportTicket.objects.filter(
        order_item=item,
        status__in=['OPEN', 'IN_PROGRESS']
    ).first()
    if existing_ticket:
        messages.info(request, f"An active dispute ticket ({existing_ticket.ticket_reference}) is already open for this item.")
        return redirect('orders:ticket_detail', reference=existing_ticket.ticket_reference)

    if request.method == 'POST':
        subject = request.POST.get('subject', f"Dispute on {item.product.name if item.product else 'Order Item'}").strip()
        description = request.POST.get('description', '').strip()
        evidence = request.FILES.get('evidence')

        if not description:
            messages.error(request, "Please describe the issue with the delivered item.")
            return redirect('orders:report_item_dispute', item_id=item.id)

        with transaction.atomic():
            item.status = 'DISPUTED'
            item.save(update_fields=['status'])

            ticket = SupportTicket.objects.create(
                user=request.user,
                category=SupportTicket.Category.PRODUCT_DISPUTE,
                priority=SupportTicket.Priority.URGENT,
                order=item.order,
                order_item=item,
                subject=subject,
                description=description,
                evidence=evidence
            )

            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=description,
                attachment=ticket.evidence.name if ticket.evidence else None,
                is_staff_reply=False
            )

        if item.product and item.product.provider and item.product.provider.user:
            _notify(
                recipient=item.product.provider.user,
                title=f"Escrow Frozen: Product Dispute ({ticket.ticket_reference})",
                message=f"The customer reported an issue with '{item.product.name}' on Order {item.order.reference}. Payout timer is paused pending review.",
                target_obj=ticket,
                notif_type='ORDER'
            )

        _notify(
            recipient=request.user,
            title=f"Escrow Frozen ({ticket.ticket_reference})",
            message=f"We paused the vendor payout timer for '{item.product.name}' while our team reviews your dispute.",
            target_obj=ticket,
            notif_type='SYSTEM'
        )

        messages.success(
            request,
            f"Escrow frozen for {item.product.name}. Ticket {ticket.ticket_reference} has been opened for arbitration."
        )
        return redirect('orders:ticket_detail', reference=ticket.ticket_reference)

    return render(request, 'support/report_item_dispute.html', {'item': item})


@login_required
def ticket_detail(request, reference):
    """
    Threaded conversation view for a SupportTicket.
    Accessible by the ticket creator, the involved vendor/provider, or staff admins.
    """
    ticket = get_object_or_404(
        SupportTicket.objects.select_related(
            'order',
            'order_item__product__provider__user',
            'service_order__provider__user',
            'service_order__service',
            'user'
        ),
        ticket_reference=reference
    )

    is_owner = request.user == ticket.user
    is_staff = request.user.is_staff or request.user.is_superuser
    is_involved_provider = False

    involved_provider_user = None
    if ticket.order_item and ticket.order_item.product and ticket.order_item.product.provider:
        involved_provider_user = ticket.order_item.product.provider.user
    elif ticket.service_order and ticket.service_order.provider:
        involved_provider_user = ticket.service_order.provider.user

    if hasattr(request.user, 'provider_profile') and involved_provider_user == request.user:
        is_involved_provider = True

    if not (is_owner or is_staff or is_involved_provider):
        return HttpResponseForbidden("You are not authorized to view this support ticket.")

    ticket.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)

    if request.method == 'POST':
        if ticket.status in ['RESOLVED_CUSTOMER', 'RESOLVED_PROVIDER', 'CLOSED'] and not is_staff:
            messages.error(request, "This ticket has already been resolved and closed.")
            return redirect('orders:ticket_detail', reference=ticket.ticket_reference)

        body = request.POST.get('body', '').strip()
        attachment = request.FILES.get('attachment')

        if body or attachment:
            msg = TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=body,
                attachment=attachment,
                is_staff_reply=is_staff
            )

            if is_staff and ticket.status == SupportTicket.Status.OPEN:
                ticket.status = SupportTicket.Status.IN_PROGRESS
                ticket.save(update_fields=['status', 'updated_at'])

            snippet = (body[:60] + '...') if len(body) > 60 else (body or 'Attached a file')

            if is_staff:
                _notify(
                    recipient=ticket.user,
                    title=f"Support Reply on {ticket.ticket_reference}",
                    message=f"AllThings Support replied: \"{snippet}\"",
                    target_obj=ticket,
                    notif_type='MESSAGE'
                )
                if involved_provider_user and involved_provider_user != ticket.user:
                    _notify(
                        recipient=involved_provider_user,
                        title=f"Support Reply on {ticket.ticket_reference}",
                        message=f"AllThings Support posted an update on dispute {ticket.ticket_reference}: \"{snippet}\"",
                        target_obj=ticket,
                        notif_type='MESSAGE'
                    )
            elif request.user == ticket.user and involved_provider_user and involved_provider_user != ticket.user:
                _notify(
                    recipient=involved_provider_user,
                    title=f"New Message on Dispute {ticket.ticket_reference}",
                    message=f"Customer replied on {ticket.ticket_reference}: \"{snippet}\"",
                    target_obj=ticket,
                    notif_type='MESSAGE'
                )
            elif is_involved_provider and ticket.user != request.user:
                _notify(
                    recipient=ticket.user,
                    title=f"Provider Responded on {ticket.ticket_reference}",
                    message=f"The provider posted a response on your ticket {ticket.ticket_reference}: \"{snippet}\"",
                    target_obj=ticket,
                    notif_type='MESSAGE'
                )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'body': msg.body,
                    'sender': 'Support Team' if msg.is_staff_reply else (msg.sender.get_full_name() or msg.sender.username),
                    'is_staff': msg.is_staff_reply,
                    'attachment_url': msg.attachment.url if msg.attachment else None,
                    'time': timezone.localtime(msg.created_at).strftime("%b %d, %I:%M %p")
                })

            messages.success(request, "Reply posted to ticket.")
        return redirect('orders:ticket_detail', reference=ticket.ticket_reference)

    context = {
        'ticket': ticket,
        'ticket_messages': ticket.messages.select_related('sender').all(),
        'is_staff': is_staff,
        'is_involved_provider': is_involved_provider,
    }
    return render(request, 'support/ticket_detail.html', context)


@login_required
def resolve_ticket(request, reference):
    """
    1-Click Admin Escrow Arbitration:
    Allows staff/admins to release frozen escrow funds to the provider,
    refund the customer, or close general support tickets.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Only marketplace administrators can arbitrate support tickets.")

    if request.method != 'POST':
        return redirect('orders:ticket_detail', reference=reference)

    ticket = get_object_or_404(
        SupportTicket.objects.select_related(
            'order_item__product__provider__user',
            'service_order__provider__user',
            'user'
        ),
        ticket_reference=reference
    )
    decision = request.POST.get('decision')
    resolution_notes = request.POST.get('resolution_notes', '').strip()

    involved_provider_user = None
    if ticket.order_item and ticket.order_item.product and ticket.order_item.product.provider:
        involved_provider_user = ticket.order_item.product.provider.user
    elif ticket.service_order and ticket.service_order.provider:
        involved_provider_user = ticket.service_order.provider.user

    with transaction.atomic():
        if decision == 'release_provider':
            if ticket.order_item and ticket.order_item.status != 'COMPLETED':
                item = ticket.order_item
                item.status = 'COMPLETED'
                item.save(update_fields=['status'])

                all_completed = not item.order.items.exclude(status='COMPLETED').exists()
                if all_completed:
                    item.order.status = 'completed'
                    item.order.save(update_fields=['status'])

                release_item_escrow(item)

            if ticket.service_order and ticket.service_order.status != 'CONFIRMED':
                s_order = ticket.service_order
                s_order.status = 'CONFIRMED'
                s_order.save(update_fields=['status'])
                if hasattr(s_order, 'dispute'):
                    s_order.dispute.status = 'RELEASED'
                    s_order.dispute.resolved_at = timezone.now()
                    s_order.dispute.admin_notes = resolution_notes
                    s_order.dispute.save(update_fields=['status', 'resolved_at', 'admin_notes'])
                release_service_escrow(s_order)

            ticket.status = SupportTicket.Status.RESOLVED_PROVIDER
            summary_msg = f"ARBITRATION DECISION: Escrow released to provider. {resolution_notes}"

        elif decision == 'refund_customer':
            if ticket.order_item:
                item = ticket.order_item
                item.status = 'REFUNDED'
                item.save(update_fields=['status'])

            if ticket.service_order:
                s_order = ticket.service_order
                s_order.status = 'CANCELLED'
                s_order.save(update_fields=['status'])
                if hasattr(s_order, 'dispute'):
                    s_order.dispute.status = 'REFUNDED'
                    s_order.dispute.resolved_at = timezone.now()
                    s_order.dispute.admin_notes = resolution_notes
                    s_order.dispute.save(update_fields=['status', 'resolved_at', 'admin_notes'])

            ticket.status = SupportTicket.Status.RESOLVED_CUSTOMER
            summary_msg = f"ARBITRATION DECISION: Disputed item/service ruled in favor of customer (Refund Approved). {resolution_notes}"

        else:
            ticket.status = SupportTicket.Status.CLOSED
            summary_msg = f"TICKET CLOSED: {resolution_notes or 'Resolved by support.'}"

        ticket.resolution_notes = resolution_notes
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'resolution_notes', 'resolved_at', 'updated_at'])

        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=summary_msg,
            is_staff_reply=True
        )

    _notify(
        recipient=ticket.user,
        title=f"Ticket {ticket.ticket_reference} Resolved: {ticket.get_status_display()}",
        message=summary_msg,
        target_obj=ticket,
        notif_type='ORDER'
    )

    if involved_provider_user and involved_provider_user != ticket.user:
        _notify(
            recipient=involved_provider_user,
            title=f"Arbitration Decision ({ticket.ticket_reference}): {ticket.get_status_display()}",
            message=summary_msg,
            target_obj=ticket,
            notif_type='ORDER'
        )

    messages.success(request, f"Ticket {ticket.ticket_reference} updated to {ticket.get_status_display()}.")
    return redirect('orders:ticket_detail', reference=ticket.ticket_reference)