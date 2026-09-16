from celery import shared_task
from django.db.models import F
from .models import Order
from .utils import process_order_commissions

@shared_task
def process_webhook_payment(order_id):
    """
    Handles the heavy lifting of order fulfillment in the background 
    after Paystack confirms a successful payment.
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # CRITICAL: Prevent double-processing if the user already hit the verify_payment view
        if not order.is_paid:
            order.is_paid = True
            order.save(update_fields=['is_paid'])
            
            # Shift physical items to PAID, generate OTPs, and Deduct Stock
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
            
            # Automatically calculate the 10% split and route funds
            process_order_commissions(order)
            
            return f"Order {order_id} fulfillment processed successfully via Webhook."
            
        return f"Order {order_id} was already marked as paid. Skipped."
        
    except Order.DoesNotExist:
        return f"Webhook Error: Order {order_id} not found in database."