import os
import re
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

# Prevent decompression bombs (max 20 Megapixels ~ 4472x4472px)
Image.MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_KYC_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

MAX_PRODUCT_IMAGES = 6
MAX_PORTFOLIO_IMAGES = 8

# Regex patterns to prevent off-platform escrow leakage
NG_PHONE_REGEX = re.compile(
    r'(?:\+?234|0)[789][01]\d[\s\-._]*\d{3}[\s\-._]*\d{4}\b'
)
NUBAN_ACCOUNT_REGEX = re.compile(r'\b\d{10}\b')
OFF_PLATFORM_PHRASES = [
    'whatsapp me', 'call me on', 'chat me on whatsapp', 'pay directly',
    'pay into my account', 'transfer to my account', 'dm on telegram',
    'outside the platform', 'call for cheaper price', 'text me on'
]


def _is_already_saved_file(file_obj):
    """
    Returns True if `file_obj` is an already-saved database/Cloudinary file
    rather than a newly uploaded file in the current request.
    Prevents Django Admin from re-validating extensionless Cloudinary public IDs.
    """
    if not file_obj:
        return True
    if getattr(file_obj, '_committed', False):
        return True
    if isinstance(file_obj, UploadedFile):
        return False
    if isinstance(getattr(file_obj, '_file', None), UploadedFile):
        return False
    return True


def validate_product_image(image_file, max_size_mb=5, min_dim=200):
    """
    Server-side image validator:
    1. Skips files already committed to storage/Cloudinary.
    2. Enforces 5MB file size limit.
    3. Checks extension allowlist (.jpg, .jpeg, .png, .webp) — blocks SVG/scripts.
    4. Decodes image header via Pillow to verify real format & guard against decompression bombs.
    """
    if _is_already_saved_file(image_file):
        return

    if image_file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"Image file size cannot exceed {max_size_mb}MB.")

    ext = os.path.splitext(image_file.name or '')[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Unsupported file extension. Please upload a JPG, PNG, or WebP image.")

    try:
        image_file.seek(0)
        with Image.open(image_file) as img:
            if img.format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError("Unsupported image format. Only JPEG, PNG, and WebP are allowed.")

            width, height = img.size
            if width < min_dim or height < min_dim:
                raise ValidationError(
                    f"Image dimensions ({width}x{height}px) are too small. Minimum required is {min_dim}x{min_dim}px."
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise ValidationError("Image resolution is too large (exceeds 20MP safety limit).")

            img.verify()
    except ValidationError:
        raise
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ValidationError("The uploaded file is corrupted or not a valid image.")
    finally:
        try:
            image_file.seek(0)
        except Exception:
            pass


def validate_kyc_document(uploaded_file, allow_pdf=True, max_size_mb=5):
    """
    Validates sensitive KYC & CAC uploads. Allows verified images (JPEG/PNG/WebP)
    and optionally PDF documents (verified via %PDF- magic header bytes).
    Skips files already committed to storage/Cloudinary.
    """
    if _is_already_saved_file(uploaded_file):
        return

    if uploaded_file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"Document size cannot exceed {max_size_mb}MB.")

    ext = os.path.splitext(uploaded_file.name or '')[1].lower()
    allowed_exts = ALLOWED_KYC_EXTENSIONS if allow_pdf else ALLOWED_IMAGE_EXTENSIONS
    if ext not in allowed_exts:
        raise ValidationError("Invalid document format. Please upload a clear JPG, PNG, WebP, or PDF.")

    if ext == '.pdf' and allow_pdf:
        uploaded_file.seek(0)
        header = uploaded_file.read(5)
        uploaded_file.seek(0)
        if header != b'%PDF-':
            raise ValidationError("Uploaded PDF file is invalid or corrupted.")
    else:
        validate_product_image(uploaded_file, max_size_mb=max_size_mb, min_dim=200)


def inspect_listing_safety(title, description, extra_texts=None, provider=None):
    """
    3-Layer Smart Moderation Gate:
    1. HARD BLOCK: Direct phone numbers, 10-digit bank accounts, or off-platform payment solicitation.
    2. SOFT FLAG: Low provider trust score (< 50) or overly short description (< 15 chars).
    """
    combined_chunks = [str(title or ''), str(description or '')]
    if extra_texts:
        combined_chunks.extend(str(t) for t in extra_texts if t)

    full_text = " ".join(combined_chunks)
    lower_text = full_text.lower()

    if NG_PHONE_REGEX.search(full_text):
        raise ValidationError(
            "Security Policy: Please remove phone numbers from your title or description. "
            "All customer communication is handled safely through the AllThings Inbox."
        )

    for phrase in OFF_PLATFORM_PHRASES:
        if phrase in lower_text:
            raise ValidationError(
                f"Security Policy: Direct off-platform solicitation ('{phrase}') is not permitted. "
                f"All transactions are protected by AllThings Escrow."
            )

    if NUBAN_ACCOUNT_REGEX.search(full_text):
        raise ValidationError(
            "Security Policy: Please remove 10-digit bank account numbers from your listing description."
        )

    if provider and getattr(provider, 'trust_score', 100) < 50:
        return True, "Held for routine admin review due to account trust score threshold."

    if len(str(description or '').strip()) < 15:
        return True, "Held for review: Please provide a more detailed technical description."

    return False, ""