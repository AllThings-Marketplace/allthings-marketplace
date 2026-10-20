from celery import shared_task
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from marketplace.models import Product, UserInteraction
from .models import Order, PaymentAttempt, ServiceOrder, OrderItem
from .utils import process_order_commissions, release_item_escrow, release_service_escrow

@shared_task
def process_webhook_payment(order_id, reference):
    """
    Handles the heavy lifting of order fulfillment in the background 
    after Paystack confirms a successful payment via Webhook.
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # 1. Log the successful payment attempt in the ledger
        PaymentAttempt.objects.filter(reference=reference).update(status='successful')
        
        # 2. CRITICAL: Prevent double-processing if the user already hit the verify_payment view
        if order.status == 'unpaid':
            order.status = 'confirmed'
            order.save(update_fields=['status'])
            
            product_ct = ContentType.objects.get_for_model(Product)
            
            # 3. Shift physical items to PAID, generate OTPs, and Deduct Stock
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
                    
                    # Log Product PURCHASE Signal (Weight = 15)
                    UserInteraction.objects.create(
                        user=order.customer,
                        content_type=product_ct,
                        object_id=item.product.id,
                        interaction_type=UserInteraction.InteractionType.PURCHASE,
                        weight=15
                    )
            
            # 4. Automatically calculate the 10% split and route funds
            process_order_commissions(order)
            
            return f"Order {order_id} fulfillment processed successfully via Webhook."
            
        return f"Order {order_id} was already marked as confirmed. Skipped."
        
    except Order.DoesNotExist:
        return f"Webhook Error: Order {order_id} not found in database."

@shared_task
def auto_clear_ghost_escrows():
    """
    Scans for delivered items and completed services older than 72 hours
    and auto-releases the funds to the provider if no dispute is open.
    """
    cutoff_time = timezone.now() - timedelta(hours=72)
    
    # --- 1. AUTO-CONFIRM SERVICES ---
    # dispute__isnull=True + support_tickets exclusion ensures disputed orders are NEVER auto-paid.
    abandoned_services = ServiceOrder.objects.filter(
        status='COMPLETED',
        completed_at__lte=cutoff_time,
        dispute__isnull=True 
    ).exclude(
        support_tickets__status__in=['OPEN', 'IN_PROGRESS']
    ).distinct()
    
    services_cleared = 0
    for service in abandoned_services:
        with transaction.atomic():
            service.status = 'CONFIRMED'
            service.save(update_fields=['status'])
            release_service_escrow(service)
            services_cleared += 1

    # --- 2. AUTO-CONFIRM PHYSICAL PRODUCTS ---
    # Double Safety Lock: Must be 'DELIVERED' (not 'DISPUTED') AND have no open support tickets.
    abandoned_items = OrderItem.objects.filter(
        status='DELIVERED',
        delivered_at__lte=cutoff_time
    ).exclude(
        support_tickets__status__in=['OPEN', 'IN_PROGRESS']
    ).distinct()
    
    items_cleared = 0
    for item in abandoned_items:
        with transaction.atomic():
            item.status = 'COMPLETED'
            item.save(update_fields=['status'])
            
            # Check if this auto-completion finishes the entire parent order
            all_completed = not item.order.items.exclude(status='COMPLETED').exists()
            if all_completed:
                item.order.status = 'completed'
                item.order.save(update_fields=['status'])
                
            # Release the physical product escrow
            release_item_escrow(item)
            items_cleared += 1
            
    return f"Auto-cleared {services_cleared} services and {items_cleared} items."