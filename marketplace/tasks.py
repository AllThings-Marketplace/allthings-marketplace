import io
import logging
import requests
import cloudinary
import cloudinary.uploader
from PIL import Image, ImageOps
from celery import shared_task
from django.core.files.base import ContentFile
from .models import Product, ProductImage, Service, ServiceImage

logger = logging.getLogger(__name__)


def _read_image_bytes(field_file):
    """Safely reads bytes from either local disk or Cloudinary storage."""
    field_file.open('rb')
    try:
        return field_file.read()
    finally:
        field_file.close()


def _local_pillow_standardize(raw_bytes, width=1080, height=1080, pad_white=True):
    """
    Offline / Fallback optimizer using Pillow so images always convert to clean WebP
    even if Cloudinary is unreachable or out of credits.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)

    if pad_white:
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            rgba = img.convert('RGBA')
            bg.paste(rgba, mask=rgba.split()[3])
            img = bg
        else:
            img = img.convert('RGB')
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (width, height), (255, 255, 255))
        offset = ((width - img.width) // 2, (height - img.height) // 2)
        canvas.paste(img, offset)
        img = canvas
    else:
        img = img.convert('RGB')
        img = ImageOps.fit(img, (width, height), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    img.save(out, format='WEBP', quality=85)
    return out.getvalue()


@shared_task
def process_service_cover_task(service_id):
    """Uses Cloudinary AI Upscaling and Smart Cropping to create a 16:9 HD banner (with Pillow fallback)."""
    try:
        service = Service.objects.select_related('provider').get(id=service_id)
        if not service.cover_image:
            return

        raw_bytes = _read_image_bytes(service.cover_image)
        optimized_bytes = None

        try:
            response = cloudinary.uploader.upload(
                raw_bytes,
                folder="marketplace_services/covers",
                transformation=[
                    {"effect": "upscale"},
                    {"width": 1280, "height": 720, "crop": "fill", "gravity": "auto"},
                    {"fetch_format": "webp", "quality": "auto"}
                ]
            )
            img_response = requests.get(response['secure_url'], timeout=30)
            if img_response.status_code == 200:
                optimized_bytes = img_response.content
        except Exception as ai_err:
            logger.warning(f"AI upscale unavailable for service {service_id}, trying standard Cloudinary crop: {ai_err}")
            try:
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
                    optimized_bytes = img_response.content
            except Exception as cloud_err:
                logger.warning(f"Cloudinary unreachable for service {service_id}, using local Pillow WebP fallback: {cloud_err}")
                optimized_bytes = _local_pillow_standardize(raw_bytes, width=1280, height=720, pad_white=False)

        if optimized_bytes:
            file_name = f"opt_cover_{service_id}.webp"
            service.cover_image.save(file_name, ContentFile(optimized_bytes), save=False)

            # Fast-track auto-approval if not flagged for manual moderation
            if (
                service.status == Service.ServiceStatus.PENDING
                and not service.moderation_note
                and service.provider
                and service.provider.verification_status == 'ACTIVE'
                and getattr(service.provider, 'trust_score', 100) >= 50
            ):
                service.status = Service.ServiceStatus.APPROVED
                service.is_active = True

            service.save()

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
        optimized_bytes = None

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
            img_response = requests.get(response['secure_url'], timeout=30)
            if img_response.status_code == 200:
                optimized_bytes = img_response.content
        except Exception as ai_err:
            logger.warning(f"AI upscale unavailable for portfolio {image_id}, using fallback: {ai_err}")
            try:
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
                    optimized_bytes = img_response.content
            except Exception:
                optimized_bytes = _local_pillow_standardize(raw_bytes, width=1080, height=1080, pad_white=True)

        if optimized_bytes:
            original_name = portfolio_img.image.name.split('/')[-1].split('.')[0]
            file_name = f"opt_port_{original_name}.webp"
            portfolio_img.image.save(file_name, ContentFile(optimized_bytes), save=True)
            
        return f"Optimized portfolio image {image_id}"

    except Exception as e:
        logger.error(f"Portfolio image optimization failed for ID {image_id}: {str(e)}")


@shared_task
def process_product_image_task(image_id):
    """
    Uses Cloudinary for Product Standardization (1080x1080 WebP) with AI + Local Pillow fallback.
    Once approved, automatically activates the parent Product if the vendor passes the Trust-Score Gate.
    """
    try:
        product_image = ProductImage.objects.select_related('product__provider').get(id=image_id)
        product_image.processing_status = 'PROCESSING'
        product_image.save(update_fields=['processing_status'])

        raw_bytes = _read_image_bytes(product_image.original_image)
        optimized_bytes = None

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
            img_response = requests.get(response['secure_url'], timeout=30)
            if img_response.status_code == 200:
                optimized_bytes = img_response.content
        except Exception as ai_err:
            logger.warning(f"AI transformation unavailable for product image {image_id}, falling back to standard WebP pad: {ai_err}")
            try:
                # 2. Automatic Fallback: Standard 1080x1080 white-padded WebP on Cloudinary
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
                    optimized_bytes = img_response.content
            except Exception as cloud_err:
                # 3. Offline / Local Pillow Fallback so products never get stuck in NEEDS_REVIEW
                logger.warning(f"Cloudinary unreachable for product image {image_id}, using local Pillow pad: {cloud_err}")
                optimized_bytes = _local_pillow_standardize(raw_bytes, width=1080, height=1080, pad_white=True)

        if optimized_bytes:
            original_name = product_image.original_image.name.split('/')[-1].split('.')[0]
            file_name = f"standardized_{original_name}.webp"
            
            product_image.processed_image.save(file_name, ContentFile(optimized_bytes), save=False)
            product_image.processing_status = 'APPROVED'
            product_image.is_approved = True
            product_image.save()

            # --- LAYER 3: TRUST-SCORE FAST-TRACK AUTO-APPROVAL ---
            product = product_image.product
            provider = product.provider
            if (
                product.status == Product.ProductStatus.PENDING
                and not product.moderation_note
                and provider
                and provider.verification_status == 'ACTIVE'
                and getattr(provider, 'trust_score', 100) >= 50
            ):
                product.status = Product.ProductStatus.APPROVED
                product.is_active = True
                product.save(update_fields=['status', 'is_active'])

        return f"Successfully processed product image {image_id}"

    except ProductImage.DoesNotExist:
        logger.error(f"Image {image_id} not found in database.")
        
    except Exception as e:
        if 'product_image' in locals():
            product_image.processing_status = 'NEEDS_REVIEW'
            product_image.rejection_reason = str(e)
            product_image.save(update_fields=['processing_status', 'rejection_reason'])
        
        logger.error(f"Failed to process image {image_id}: {str(e)}")