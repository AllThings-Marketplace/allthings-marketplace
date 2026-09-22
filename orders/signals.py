from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import ServiceOrder
from .utils import release_service_escrow, refund_service_escrow

@receiver(pre_save, sender=ServiceOrder)
def automate_service_escrow(sender, instance, **kwargs):
    if instance.pk:
        old_order = ServiceOrder.objects.get(pk=instance.pk)
        
        # Scenario A: The job is confirmed (Provider wins / Job Done)
        if old_order.status != 'CONFIRMED' and instance.status == 'CONFIRMED':
            release_service_escrow(instance)
            
        # Scenario B: The job is cancelled or refunded (Customer wins)
        elif old_order.status not in ['CANCELLED', 'REFUNDED'] and instance.status in ['CANCELLED', 'REFUNDED']:
            refund_service_escrow(instance)