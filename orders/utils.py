import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from accounts.models import VendorWallet, VendorTransaction

logger = logging.getLogger(__name__)

COMMISSION_RATE = Decimal('0.10')  # 10% Platform Fee


def process_order_commissions(order):
    """
    Idempotently calculates the 10% platform commission for each OrderItem
    and credits the provider's locked VendorWallet.pending_balance.
    Safe against multi-item caching bugs and concurrent webhook calls.
    """
    for item in order.items.select_related('product__provider').all():
        provider = getattr(item.product, 'provider', None) if item.product else None
        if not provider:
            continue

        txn_ref = f"ORD-{order.id}-ITEM-{item.id}"

        with transaction.atomic():
            wallet, _ = VendorWallet.objects.select_for_update().get_or_create(provider=provider)

            # Idempotency guard: never double-create or double-credit the same order item
            if VendorTransaction.objects.filter(reference=txn_ref).exists():
                continue

            gross_amount = Decimal(str(item.get_total)).quantize(Decimal('0.01'))
            commission = (gross_amount * COMMISSION_RATE).quantize(Decimal('0.01'))
            net_amount = gross_amount - commission

            VendorTransaction.objects.create(
                wallet=wallet,
                order=order,
                transaction_type='SALE',
                gross_amount=gross_amount,
                commission=commission,
                net_amount=net_amount,
                reference=txn_ref,
                status='PENDING',
            )

            wallet.pending_balance += net_amount
            wallet.save(update_fields=['pending_balance', 'last_updated'])


def release_item_escrow(item):
    """
    Atomically unlocks escrow funds for a specific OrderItem after delivery confirmation
    or 72-hour auto-clearance. Row-locked so double-clicks can never double-pay.
    """
    txn_ref = f"ORD-{item.order_id}-ITEM-{item.id}"

    with transaction.atomic():
        txn = (
            VendorTransaction.objects.select_for_update()
            .filter(reference=txn_ref, status='PENDING')
            .first()
        )
        if not txn:
            return False

        wallet = VendorWallet.objects.select_for_update().get(id=txn.wallet_id)
        wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - txn.net_amount)
        wallet.available_balance += txn.net_amount
        wallet.save(update_fields=['pending_balance', 'available_balance', 'last_updated'])

        txn.status = 'CLEARED'
        txn.cleared_at = timezone.now()
        txn.save(update_fields=['status', 'cleared_at'])
        return True


def refund_item_escrow(item):
    """
    Atomically removes pending escrow funds from the vendor's wallet when a paid
    OrderItem is cancelled or refunded during dispute arbitration.
    """
    txn_ref = f"ORD-{item.order_id}-ITEM-{item.id}"

    with transaction.atomic():
        txn = (
            VendorTransaction.objects.select_for_update()
            .filter(reference=txn_ref, status='PENDING')
            .first()
        )
        if not txn:
            return False

        wallet = VendorWallet.objects.select_for_update().get(id=txn.wallet_id)
        wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - txn.net_amount)
        wallet.save(update_fields=['pending_balance', 'last_updated'])

        txn.transaction_type = 'REFUND'
        txn.status = 'FAILED'
        txn.cleared_at = timezone.now()
        txn.save(update_fields=['transaction_type', 'status', 'cleared_at'])
        return True


def dispatch_gigl_rider(item):
    """
    Prepares and dispatches a pickup request to the logistics gateway.
    """
    if not item.product or not item.product.provider:
        return None

    url = "https://api.giglogistics.com/v1/shipments"
    headers = {
        "Authorization": f"Bearer {getattr(settings, 'GIGL_API_KEY', '')}",
        "Content-Type": "application/json",
    }

    payload = {
        "senderName": item.product.provider.business_name,
        "senderAddress": item.product.provider.store_address,
        "receiverName": f"{item.order.first_name} {item.order.last_name}",
        "receiverAddress": item.order.street_address,
        "receiverPhoneNumber": item.order.phone,
        "itemName": item.product.name,
        "quantity": item.quantity,
        "specialInstruction": f"Provide PIN {item.pickup_code} to vendor upon pickup.",
    }
    return payload


def create_service_escrow(service_order):
    """
    Idempotently creates a pending escrow ledger entry when a customer pays
    for a ServiceOrder and credits the provider's pending_balance.
    """
    provider = service_order.provider
    if not provider or not service_order.agreed_price:
        return None

    txn_ref = f"SRV-{service_order.reference_code}"

    with transaction.atomic():
        wallet, _ = VendorWallet.objects.select_for_update().get_or_create(provider=provider)

        existing_txn = VendorTransaction.objects.filter(reference=txn_ref).first()
        if existing_txn:
            return existing_txn

        gross_amount = Decimal(str(service_order.agreed_price)).quantize(Decimal('0.01'))
        commission = (gross_amount * COMMISSION_RATE).quantize(Decimal('0.01'))
        net_amount = gross_amount - commission

        txn = VendorTransaction.objects.create(
            wallet=wallet,
            transaction_type='SALE',
            gross_amount=gross_amount,
            commission=commission,
            net_amount=net_amount,
            reference=txn_ref,
            status='PENDING',
        )

        wallet.pending_balance += net_amount
        wallet.save(update_fields=['pending_balance', 'last_updated'])
        return txn


def release_service_escrow(service_order):
    """
    Atomically releases pending escrow funds into the service provider's
    available wallet balance. Row-locked against concurrent calls.
    """
    txn_ref = f"SRV-{service_order.reference_code}"

    with transaction.atomic():
        txn = (
            VendorTransaction.objects.select_for_update()
            .filter(reference=txn_ref, status='PENDING')
            .first()
        )
        if not txn:
            return False

        wallet = VendorWallet.objects.select_for_update().get(id=txn.wallet_id)
        wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - txn.net_amount)
        wallet.available_balance += txn.net_amount
        wallet.save(update_fields=['pending_balance', 'available_balance', 'last_updated'])

        txn.status = 'CLEARED'
        txn.cleared_at = timezone.now()
        txn.save(update_fields=['status', 'cleared_at'])
        return True


def refund_service_escrow(service_order):
    """
    Atomically reverses pending escrow funds if a paid service booking is
    cancelled or ruled in favor of the customer during arbitration.
    """
    txn_ref = f"SRV-{service_order.reference_code}"

    with transaction.atomic():
        txn = (
            VendorTransaction.objects.select_for_update()
            .filter(reference=txn_ref, status='PENDING')
            .first()
        )
        if not txn:
            return False

        wallet = VendorWallet.objects.select_for_update().get(id=txn.wallet_id)
        wallet.pending_balance = max(Decimal('0.00'), wallet.pending_balance - txn.net_amount)
        wallet.save(update_fields=['pending_balance', 'last_updated'])

        txn.transaction_type = 'REFUND'
        txn.status = 'FAILED'
        txn.cleared_at = timezone.now()
        txn.save(update_fields=['transaction_type', 'status', 'cleared_at'])
        return True