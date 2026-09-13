import logging
from celery import shared_task
from django.core.files.base import ContentFile
from .models import ProductImage
from .utils.image_processor import MarketImageProcessor

logger = logging.getLogger(__name__)

@shared_task
def process_product_image_task(image_id):
    try:
        # 1. Fetch the image record and lock the status
        product_image = ProductImage.objects.get(id=image_id)
        product_image.processing_status = 'PROCESSING'
        product_image.save(update_fields=['processing_status'])

        # 2. Read the raw uploaded bytes
        raw_bytes = product_image.original_image.read()

        # 3. Route through the AI Background Removal and Standardization engine
        processed_bytes = MarketImageProcessor.process_main_image(raw_bytes)

        # 4. Generate a clean filename and save it to the processed_image field
        original_name = product_image.original_image.name.split('/')[-1]
        file_name = f"standardized_{original_name}"
        
        # save=False prevents a premature database commit before we update the status
        product_image.processed_image.save(file_name, ContentFile(processed_bytes), save=False)
        
        # 5. Mark as successful and push to the marketplace
        product_image.processing_status = 'APPROVED'
        product_image.is_approved = True
        product_image.save()

        return f"Successfully processed image {image_id}"

    except ProductImage.DoesNotExist:
        logger.error(f"Image {image_id} not found in database.")
        
    except Exception as e:
        # 6. Graceful Failure: If the AI struggles, flag for a human to review
        if 'product_image' in locals():
            product_image.processing_status = 'NEEDS_REVIEW'
            product_image.rejection_reason = str(e)
            product_image.save(update_fields=['processing_status', 'rejection_reason'])
        
        logger.error(f"Failed to process image {image_id}: {str(e)}")