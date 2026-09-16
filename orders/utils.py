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
    url = "https://api.giglogistics.com/v1/shipments" # Example endpoint
    headers = {
        "Authorization": f"Bearer {settings.GIGL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "senderName": item.product.provider.business_name,
        "senderAddress": item.product.provider.address,
        "receiverName": f"{item.order.first_name} {item.order.last_name}",
        "receiverAddress": item.order.street_address,
        "receiverPhoneNumber": item.order.phone,
        "itemName": item.product.name,
        "quantity": item.quantity,
        # We pass your custom pickup code in the delivery notes for the rider
        "specialInstruction": f"Provide PIN {item.pickup_code} to vendor upon pickup."
    }
    
    # response = requests.post(url, json=payload, headers=headers)
    # return response.json()

def create_job_escrow(job):
    """
    Creates a pending escrow ledger entry when a technician accepts a paid job.
    """
    COMMISSION_RATE = Decimal('0.10') # 10% Platform Fee
    provider_profile = getattr(job.provider, 'provider_profile', None)
    
    if provider_profile and hasattr(provider_profile, 'wallet') and job.service:
        wallet = provider_profile.wallet
        gross_amount = job.service.base_price
        commission = gross_amount * COMMISSION_RATE
        net_amount = gross_amount - commission
        
        VendorTransaction.objects.create(
            wallet=wallet,
            order=job.order,
            transaction_type='SERVICE',
            gross_amount=gross_amount,
            commission=commission,
            net_amount=net_amount,
            reference=f"ORD-{job.order.id}-JOB-{job.id}",
            status='PENDING'
        )
        
        wallet.pending_balance += net_amount
        wallet.save()

def release_job_escrow(job):
    """
    Releases pending escrow funds into the technician's available wallet balance.
    """
    txn_ref = f"ORD-{job.order.id}-JOB-{job.id}"
    txn = VendorTransaction.objects.filter(reference=txn_ref, status='PENDING').first()
    
    if txn:
        wallet = txn.wallet
        wallet.pending_balance -= txn.net_amount
        wallet.available_balance += txn.net_amount
        wallet.save()
        
        txn.status = 'CLEARED'
        txn.cleared_at = timezone.now()
        txn.save()