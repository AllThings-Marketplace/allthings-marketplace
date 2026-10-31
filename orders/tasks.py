import logging
import threading
from datetime import timedelta
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from marketplace.models import Product, UserInteraction
from .models import Order, PaymentAttempt, ServiceOrder, OrderItem
from .utils import process_order_commissions, release_item_escrow, release_service_escrow

logger = logging.getLogger(__name__)

ESCROW_MAINTENANCE_CACHE_KEY = "allthings:last_escrow_auto_clear"
ESCROW_MAINTENANCE_INTERVAL_SECONDS = 1800  # Run at most once every 30 minutes


@shared_task
def process_webhook_payment(order_id, reference):
    """
    Handles order fulfillment in the background after Paystack confirms payment.
    Uses row-level locking (`select_for_update`) inside `transaction.atomic()`
    so concurrent webhook + browser verification requests never double-credit wallets.
    """
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            # 1. Log the successful payment attempt in the ledger
            PaymentAttempt.objects.filter(reference=reference).update(status='successful')

            # 2. Idempotency Guard: Skip if verify_payment already confirmed this order
            if order.status != 'unpaid':
                return f"Order {order_id} was already marked as {order.status}. Skipped."

            order.status = 'confirmed'
            order.save(update_fields=['status'])

            product_ct = ContentType.objects.get_for_model(Product)

            # 3. Shift physical items to PAID, generate OTPs, and safely deduct stock
            for item in order.items.select_related('product', 'variant').all():
                item.status = 'PAID'
                item.save(update_fields=['status'])
                item.generate_handshake_codes()

                if item.variant:
                    item.variant.stock = Greatest(F('stock') - item.quantity, 0)
                    item.variant.save(update_fields=['stock'])

                if item.product:
                    item.product.stock_count = Greatest(F('stock_count') - item.quantity, 0)
                    item.product.save(update_fields=['stock_count'])

                    UserInteraction.objects.create(
                        user=order.customer,
                        content_type=product_ct,
                        object_id=item.product.id,
                        interaction_type=UserInteraction.InteractionType.PURCHASE,
                        weight=15,
                    )

            # 4. Calculate the 10% platform split and credit provider pending balances
            process_order_commissions(order)

        return f"Order {order_id} fulfillment processed successfully via Webhook."

    except Order.DoesNotExist:
        return f"Webhook Error: Order {order_id} not found in database."


@shared_task
def auto_clear_ghost_escrows():
    """
    Scans for delivered items and completed services older than 72 hours
    and auto-releases the funds to the provider if no dispute is open.
    Each row is re-verified under `select_for_update()` to prevent double payouts.
    """
    cutoff_time = timezone.now() - timedelta(hours=72)

    # --- 1. AUTO-CONFIRM SERVICES ---
    candidate_service_ids = list(
        ServiceOrder.objects.filter(
            status='COMPLETED',
            completed_at__lte=cutoff_time,
            dispute__isnull=True,
        ).exclude(
            support_tickets__status__in=['OPEN', 'IN_PROGRESS']
        ).values_list('id', flat=True).distinct()
    )

    services_cleared = 0
    for service_id in candidate_service_ids:
        with transaction.atomic():
            service_order = (
                ServiceOrder.objects.select_for_update()
                .filter(
                    id=service_id,
                    status='COMPLETED',
                    completed_at__lte=cutoff_time,
                    dispute__isnull=True,
                )
                .exclude(support_tickets__status__in=['OPEN', 'IN_PROGRESS'])
                .first()
            )
            if not service_order:
                continue

            service_order.status = 'CONFIRMED'
            service_order.save(update_fields=['status'])
            release_service_escrow(service_order)
            services_cleared += 1

    # --- 2. AUTO-CONFIRM PHYSICAL PRODUCTS ---
    candidate_item_ids = list(
        OrderItem.objects.filter(
            status='DELIVERED',
            delivered_at__lte=cutoff_time,
        ).exclude(
            support_tickets__status__in=['OPEN', 'IN_PROGRESS']
        ).values_list('id', flat=True).distinct()
    )

    items_cleared = 0
    for item_id in candidate_item_ids:
        with transaction.atomic():
            item = (
                OrderItem.objects.select_for_update()
                .select_related('order')
                .filter(
                    id=item_id,
                    status='DELIVERED',
                    delivered_at__lte=cutoff_time,
                )
                .exclude(support_tickets__status__in=['OPEN', 'IN_PROGRESS'])
                .first()
            )
            if not item:
                continue

            item.status = 'COMPLETED'
            item.save(update_fields=['status'])

            all_completed = not item.order.items.exclude(status='COMPLETED').exists()
            if all_completed and item.order.status != 'completed':
                item.order.status = 'completed'
                item.order.save(update_fields=['status'])

            release_item_escrow(item)
            items_cleared += 1

    return f"Auto-cleared {services_cleared} services and {items_cleared} items."


def trigger_escrow_auto_clear_if_due():
    """
    Lightweight, cache-throttled trigger so `auto_clear_ghost_escrows` runs reliably
    every 30 minutes on single-container Railway deployments even without Celery Beat.
    """
    if not cache.add(ESCROW_MAINTENANCE_CACHE_KEY, True, timeout=ESCROW_MAINTENANCE_INTERVAL_SECONDS):
        return

    def _run():
        try:
            auto_clear_ghost_escrows()
        except Exception as exc:
            logger.warning("Background escrow auto-clear check failed: %s", exc)

    threading.Thread(target=_run, daemon=True).start()