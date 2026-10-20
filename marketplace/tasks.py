import logging
import requests
import cloudinary
import cloudinary.uploader
from celery import shared_task
from django.core.files.base import ContentFile
from .models import ProductImage, Service, ServiceImage

logger = logging.getLogger(__name__)

def _read_image_bytes(field_file):
    """Safely reads bytes from either local disk or Cloudinary storage."""
    field_file.open('rb')
    try:
        return field_file.read()
    finally:
        field_file.close()


@shared_task
def process_service_cover_task(service_id):
    """Uses Cloudinary AI Upscaling and Smart Cropping to create a 16:9 HD banner."""
    try:
        service = Service.objects.get(id=service_id)
        if not service.cover_image:
            return

        raw_bytes = _read_image_bytes(service.cover_image)

        try:
            # 1. Try with AI Super Resolution upscale
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_services/covers",
                transformation=[
                    {"effect": "upscale"},
                    {"width": 1280, "height": 720, "crop": "fill", "gravity": "auto"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )
        except Exception as ai_err:
            logger.warning(f"AI upscale unavailable for service {service_id}, using standard crop: {ai_err}")
            # 2. Fallback to standard smart-crop if AI transformation fails
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_services/covers",
                transformation=[
                    {"width": 1280, "height": 720, "crop": "fill", "gravity": "auto"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )

        img_response = requests.get(response['secure_url'], timeout=30)
        if img_response.status_code == 200:
            file_name = f"opt_cover_{service_id}.webp"
            service.cover_image.save(file_name, ContentFile(img_response.content), save=True)
        
        return f"Optimized cover for Service {service_id}"

    except Exception as e:
        logger.error(f"Cover image optimization failed for service {service_id}: {str(e)}")


@shared_task
def process_service_portfolio_task(image_id):
    """Enhances portfolio images into optimized WebP format while maintaining proportions."""
    try:
        portfolio_img = ServiceImage.objects.get(id=image_id)
        if not portfolio_img.image:
            return

        raw_bytes = _read_image_bytes(portfolio_img.image)

        try:
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_services/portfolio",
                transformation=[
                    {"effect": "upscale"},
                    {"width": 1080, "height": 1080, "crop": "limit"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )
        except Exception as ai_err:
            logger.warning(f"AI upscale unavailable for portfolio {image_id}, using standard resize: {ai_err}")
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_services/portfolio",
                transformation=[
                    {"width": 1080, "height": 1080, "crop": "limit"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )

        img_response = requests.get(response['secure_url'], timeout=30)
        if img_response.status_code == 200:
            original_name = portfolio_img.image.name.split('/')[-1].split('.')[0]
            file_name = f"opt_port_{original_name}.webp"
            portfolio_img.image.save(file_name, ContentFile(img_response.content), save=True)
            
        return f"Optimized portfolio image {image_id}"

    except Exception as e:
        logger.error(f"Portfolio image optimization failed for ID {image_id}: {str(e)}")


@shared_task
def process_product_image_task(image_id):
    """Uses Cloudinary for Product Standardization (1080x1080 WebP) with AI fallback."""
    try:
        product_image = ProductImage.objects.get(id=image_id)
        product_image.processing_status = 'PROCESSING'
        product_image.save(update_fields=['processing_status'])

        raw_bytes = _read_image_bytes(product_image.original_image)

        try:
            # 1. Built-in AI Background Removal + Super Resolution inside transformation
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_products",
                transformation=[
                    {"effect": "background_removal"},
                    {"effect": "upscale"},
                    {"width": 1080, "height": 1080, "crop": "pad", "background": "white"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )
        except Exception as ai_err:
            logger.warning(f"AI transformation unavailable for product image {image_id}, falling back to standard WebP pad: {ai_err}")
            # 2. Automatic Fallback: Standard 1080x1080 white-padded WebP
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_products",
                transformation=[
                    {"width": 1080, "height": 1080, "crop": "pad", "background": "white"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )

        img_response = requests.get(response['secure_url'], timeout=30)
        if img_response.status_code == 200:
            original_name = product_image.original_image.name.split('/')[-1].split('.')[0]
            file_name = f"standardized_{original_name}.webp"
            
            product_image.processed_image.save(file_name, ContentFile(img_response.content), save=False)
            product_image.processing_status = 'APPROVED'
            product_image.is_approved = True
            product_image.save()

        return f"Successfully processed product image {image_id}"

    except ProductImage.DoesNotExist:
        logger.error(f"Image {image_id} not found in database.")
        
    except Exception as e:
        if 'product_image' in locals():
            product_image.processing_status = 'NEEDS_REVIEW'
            product_image.rejection_reason = str(e)
            product_image.save(update_fields=['processing_status', 'rejection_reason'])
        
        logger.error(f"Failed to process image {image_id}: {str(e)}")