import io
from PIL import Image
from rembg import remove

class MarketImageProcessor:
    CANVAS_SIZE = (2000, 2000)
    PRODUCT_SCALE = 0.8  # Product takes up 80% of the canvas
    BACKGROUND_COLOR = (255, 255, 255) # Pure white
    
    @staticmethod
    def process_main_image(image_bytes):
        # 1. Open the raw uploaded image
        raw_image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        
        # 2. AI Background Removal
        no_bg_image = remove(raw_image)
        
        # 3. Find the exact edges of the product (ignoring transparent space)
        bbox = no_bg_image.getbbox()
        if not bbox:
            raise ValueError("No product detected in the image.")
            
        cropped_product = no_bg_image.crop(bbox)
        
        # 4. Calculate new dimensions to fit the 80% scale constraint
        target_width = int(MarketImageProcessor.CANVAS_SIZE[0] * MarketImageProcessor.PRODUCT_SCALE)
        target_height = int(MarketImageProcessor.CANVAS_SIZE[1] * MarketImageProcessor.PRODUCT_SCALE)
        
        # Resize smoothly while maintaining the original aspect ratio
        cropped_product.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 5. Generate the standardized pure white canvas
        final_image = Image.new("RGB", MarketImageProcessor.CANVAS_SIZE, MarketImageProcessor.BACKGROUND_COLOR)
        
        # 6. Calculate coordinates to perfectly center the product
        paste_x = (MarketImageProcessor.CANVAS_SIZE[0] - cropped_product.width) // 2
        paste_y = (MarketImageProcessor.CANVAS_SIZE[1] - cropped_product.height) // 2
        
        # 7. Paste the product onto the canvas (using its own transparency as a mask)
        final_image.paste(cropped_product, (paste_x, paste_y), cropped_product)
        
        # 8. Compress and convert back to bytes for Django storage
        output_io = io.BytesIO()
        final_image.save(output_io, format='JPEG', quality=90)
        
        return output_io.getvalue()