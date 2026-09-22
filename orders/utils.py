from django.conf import settings
from decimal import Decimal
from accounts.models import VendorTransaction
from django.utils import timezone

def process_order_commissions(order):
    """
    Called immediately after Paystack verifies a successful payment.
    Calculates the 10% commission and routes funds to vendor wallets.
    """
    COMMISSION_RATE = Decimal('0.10') # 10% Platform Fee
    
    # 1. Route Funds for Physical Products
    for item in order.items.all():
        # Ensure the product actually belongs to a registered provider with a wallet
        if item.product and getattr(item.product, 'provider', None) and hasattr(item.product.provider, 'wallet'):
            wallet = item.product.provider.wallet
            
            # get_total is a property, so no parentheses needed
            gross_amount = item.get_total 
            commission = gross_amount * COMMISSION_RATE
            net_amount = gross_amount - commission
            
            # Create the immutable ledger record
            VendorTransaction.objects.create(
                wallet=wallet,
                order=order,
                transaction_type='SALE',
                gross_amount=gross_amount,
                commission=commission,
                net_amount=net_amount,
                reference=f"ORD-{order.id}-ITEM-{item.id}",
                status='PENDING'
            )
            
            # Securely increase the vendor's pending escrow balance
            wallet.pending_balance += net_amount
            wallet.save()

def release_item_escrow(item):
    """
    Unlocks funds for a specific vendor item after delivery confirmation.
    """
    # Match the exact reference created in process_order_commissions
    txn_ref = f"ORD-{item.order.id}-ITEM-{item.id}"
    
    # Find the specific pending transaction for this exact product
    txn = VendorTransaction.objects.filter(reference=txn_ref, status='PENDING').first()
    
    if txn:
        wallet = txn.wallet
        
        # 1. Deduct from escrow
        wallet.pending_balance -= txn.net_amount
        
        # 2. Add to withdrawable balance
        wallet.available_balance += txn.net_amount
        wallet.save()
        
        # 3. Permanently clear the ledger record
        txn.status = 'CLEARED'
        txn.cleared_at = timezone.now()
        txn.save()

def dispatch_gigl_rider(item):
    """
    Triggers a pickup request to the GIGL API.
    """
    url = "https://api.giglogistics.com/v1/shipments" 
    headers = {
        "Authorization": f"Bearer {settings.GIGL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "senderName": item.product.provider.business_name,
        
        # THE FIX: Updated from .address to .store_address
        "senderAddress": item.product.provider.store_address, 
        
        "receiverName": f"{item.order.first_name} {item.order.last_name}",
        "receiverAddress": item.order.street_address,
        "receiverPhoneNumber": item.order.phone,
        "itemName": item.product.name,
        "quantity": item.quantity,
        "specialInstruction": f"Provide PIN {item.pickup_code} to vendor upon pickup."
    }
    
    # response = requests.post(url, json=payload, headers=headers)
    # return response.json()

def create_service_escrow(service_order):
    """
    Creates a pending escrow ledger entry when a customer successfully pays for a service request.
    """
    COMMISSION_RATE = Decimal('0.10') # 10% Platform Fee
    provider_profile = service_order.provider
    
    if provider_profile and hasattr(provider_profile, 'wallet') and service_order.agreed_price:
        wallet = provider_profile.wallet
        gross_amount = service_order.agreed_price
        commission = gross_amount * COMMISSION_RATE
        net_amount = gross_amount - commission
        
        VendorTransaction.objects.create(
            wallet=wallet,
            transaction_type='SERVICE',
            gross_amount=gross_amount,
            commission=commission,
            net_amount=net_amount,
            reference=f"SRV-{service_order.reference_code}",
            status='PENDING'
        )
        
        # Securely increase the vendor's pending escrow balance
        wallet.pending_balance += net_amount
        wallet.save()

def release_service_escrow(service_order):
    """
    Releases pending escrow funds into the service provider's available wallet balance.
    """
    txn_ref = f"SRV-{service_order.reference_code}"
    txn = VendorTransaction.objects.filter(reference=txn_ref, status='PENDING').first()
    
    if txn:
        wallet = txn.wallet
        
        # 1. Deduct from escrow
        wallet.pending_balance -= txn.net_amount
        
        # 2. Add to withdrawable balance
        wallet.available_balance += txn.net_amount
        wallet.save()
        
        # 3. Permanently clear the ledger record
        txn.status = 'CLEARED'
        txn.cleared_at = timezone.now()
        txn.save()

def refund_service_escrow(service_order):
    """
    Wipes pending escrow funds if a service is cancelled or a dispute is lost.
    """
    txn_ref = f"SRV-{service_order.reference_code}"
    txn = VendorTransaction.objects.filter(reference=txn_ref, status='PENDING').first()
    
    if txn:
        wallet = txn.wallet
        # Deduct from escrow, but DO NOT add to available balance
        wallet.pending_balance -= txn.net_amount
        wallet.save()
        
        # Permanently mark the ledger record as refunded
        txn.status = 'REFUNDED'
        txn.save()