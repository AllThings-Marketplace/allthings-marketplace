from django.core.exceptions import ValidationError
from PIL import Image

def validate_product_image(file):
    # 1. File Size Restriction (5MB)
    max_size_mb = 5
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"Image file too large ( > {max_size_mb}MB ).")

    # 2. Deep Integrity Check (Prevents malicious files)
    try:
        img = Image.open(file)
        img.verify() # Analyzes the file header to ensure it's a real image
        
        # Reset the file pointer to the beginning after verify()
        file.seek(0)
        img = Image.open(file)
            
        # 3. Format Restriction
        valid_formats = ['JPEG', 'MPO', 'PNG', 'WEBP']
        if img.format not in valid_formats:
            raise ValidationError(f"Unsupported format: {img.format}. Allowed: JPEG, PNG, WEBP.")
            
    except ValidationError as e:
        raise e
    except Exception:
        raise ValidationError("The uploaded file is corrupted or not a valid image.")