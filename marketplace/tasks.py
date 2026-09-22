import logging
import requests
import cloudinary
import cloudinary.uploader
from celery import shared_task
from django.core.files.base import ContentFile
from .models import ProductImage, Service, ServiceImage

logger = logging.getLogger(__name__)

@shared_task
def process_service_cover_task(service_id):
    """Uses Cloudinary AI Upscaling and Smart Cropping to create a perfect 16:9 HD banner."""
    try:
        service = Service.objects.get(id=service_id)
        if not service.cover_image:
            return

        raw_bytes = service.cover_image.read()

        # Upload to Cloudinary & apply AI transformations
        response = cloudinary.uploader.upload(
            raw_bytes,
            folder="marketplace_services/covers",
            transformation=[
                {"effect": "upscale"}, # AI Super Resolution (rebuilds blurry pixels)
                {"width": 1280, "height": 720, "crop": "fill", "gravity": "auto"}, # AI-aware smart crop
                {"fetch_format": "webp", "quality": "auto"} # Next-gen compression
            ]
        )

        # Download the AI-processed image back to your Django server
        img_response = requests.get(response['secure_url'])
        if img_response.status_code == 200:
            file_name = f"opt_cover_{service_id}.webp"
            # Overwrite the old image with the new HD image
            service.cover_image.save(file_name, ContentFile(img_response.content), save=True)
        
        return f"AI Optimized cover for Service {service_id}"

    except Exception as e:
        logger.error(f"Cover image optimization failed for service {service_id}: {str(e)}")


@shared_task
def process_service_portfolio_task(image_id):
    """Uses Cloudinary AI Upscaling to enhance blurry portfolio images while maintaining proportions."""
    try:
        portfolio_img = ServiceImage.objects.get(id=image_id)
        if not portfolio_img.image:
            return

        raw_bytes = portfolio_img.image.read()

        response = cloudinary.uploader.upload(
            raw_bytes,
            folder="marketplace_services/portfolio",
            transformation=[
                {"effect": "upscale"},
                {"width": 1080, "height": 1080, "crop": "limit"}, # Caps max size, doesn't stretch
                {"fetch_format": "webp", "quality": "auto"}
            ]
        )

        img_response = requests.get(response['secure_url'])
        if img_response.status_code == 200:
            original_name = portfolio_img.image.name.split('/')[-1].split('.')[0]
            file_name = f"opt_port_{original_name}.webp"
            portfolio_img.image.save(file_name, ContentFile(img_response.content), save=True)
            
        return f"AI Optimized portfolio image {image_id}"

    except Exception as e:
        logger.error(f"Portfolio image optimization failed for ID {image_id}: {str(e)}")


@shared_task
def process_product_image_task(image_id):
    """Uses Cloudinary for Product Standardization and AI Upscaling."""
    try:
        product_image = ProductImage.objects.get(id=image_id)
        product_image.processing_status = 'PROCESSING'
        product_image.save(update_fields=['processing_status'])

        raw_bytes = product_image.original_image.read()

        response = cloudinary.uploader.upload(
            raw_bytes,
            folder="marketplace_products",
            background_removal="cloudinary_ai",
            transformation=[
                {"effect": "upscale"},
                {"width": 1080, "height": 1080, "crop": "pad", "background": "white"},
                {"fetch_format": "webp", "quality": "auto"}
            ]
        )

        img_response = requests.get(response['secure_url'])
        if img_response.status_code == 200:
            original_name = product_image.original_image.name.split('/')[-1].split('.')[0]
            file_name = f"standardized_{original_name}.webp"
            
            product_image.processed_image.save(file_name, ContentFile(img_response.content), save=False)
            
            product_image.processing_status = 'APPROVED'
            product_image.is_approved = True
            product_image.save()

        return f"Successfully AI-processed image {image_id}"

    except ProductImage.DoesNotExist:
        logger.error(f"Image {image_id} not found in database.")
        
    except Exception as e:
        if 'product_image' in locals():
            product_image.processing_status = 'NEEDS_REVIEW'
            product_image.rejection_reason = str(e)
            product_image.save(update_fields=['processing_status', 'rejection_reason'])
        
        logger.error(f"Failed to process image {image_id}: {str(e)}")