from django.core.management.base import BaseCommand
from marketplace.models import Category

class Command(BaseCommand):
    help = 'Bulk updates existing categories with their dynamic JSON attribute schemas'

    def handle(self, *args, **kwargs):
        self.stdout.write("Injecting broad category attributes...")

        # Base schemas to reuse
        TECH_BASE = [
            {"name": "Brand", "required": True},
            {"name": "Condition (New/Used/Refurbished)", "required": True},
            {"name": "Warranty Period", "required": False}
        ]
        FASHION_BASE = [
            {"name": "Brand", "required": False},
            {"name": "Material", "required": True},
            {"name": "Gender (Men/Women/Unisex)", "required": False}
        ]
        SERVICE_BASE = [
            {"name": "Service Mode (Remote/On-site)", "required": True},
            {"name": "Estimated Duration", "required": True},
            {"name": "Service Level (Basic/Premium/Enterprise)", "required": False}
        ]
        UNIVERSAL_FALLBACK = [
            {"name": "Brand/Manufacturer", "required": False},
            {"name": "Condition (New/Used)", "required": False}
        ]

        # Specific mapping for precision
        ATTRIBUTE_MAPPING = {
            # Tech & Electronics
            "Gaming Laptops": TECH_BASE + [{"name": "RAM", "required": True}, {"name": "GPU", "required": True}, {"name": "Processor", "required": True}],
            "Business Laptops": TECH_BASE + [{"name": "RAM", "required": True}, {"name": "Processor", "required": True}, {"name": "Storage", "required": True}],
            "MacBooks": TECH_BASE + [{"name": "Chip (M1/M2/M3)", "required": True}, {"name": "RAM", "required": True}, {"name": "Storage", "required": True}],
            "Android Phones": TECH_BASE + [{"name": "RAM", "required": True}, {"name": "Internal Storage", "required": True}, {"name": "Battery (mAh)", "required": False}],
            "iOS Devices": TECH_BASE + [{"name": "Storage", "required": True}, {"name": "Battery Health (%)", "required": False}],
            "Power Banks": TECH_BASE + [{"name": "Capacity (mAh)", "required": True}, {"name": "Output Ports", "required": True}],
            
            # Electrical & Power
            "Generators": TECH_BASE + [{"name": "Power Output (kVA/kW)", "required": True}, {"name": "Fuel Type", "required": True}, {"name": "Starting System", "required": True}],
            "Solar Panels": TECH_BASE + [{"name": "Wattage (W)", "required": True}, {"name": "Cell Type (Mono/Poly)", "required": True}],
            "Deep Cycle Batteries": TECH_BASE + [{"name": "Voltage (V)", "required": True}, {"name": "Capacity (Ah)", "required": True}, {"name": "Chemistry", "required": True}],
            "Copper Cables": [{"name": "Length (Meters/Coil)", "required": True}, {"name": "Thickness (mm)", "required": True}],
            
            # Home & Appliances
            "AC Units": TECH_BASE + [{"name": "Horsepower (HP)", "required": True}, {"name": "Inverter Technology (Yes/No)", "required": True}],
            "Refrigerators": TECH_BASE + [{"name": "Capacity (Liters)", "required": True}, {"name": "Type (Single/Double Door)", "required": True}],
            
            # Fashion
            "Shirts": FASHION_BASE + [{"name": "Size (S/M/L/XL)", "required": True}, {"name": "Fit (Slim/Regular)", "required": False}],
            "Sneakers": FASHION_BASE + [{"name": "Shoe Size (EU/US)", "required": True}, {"name": "Closure Type", "required": False}],
            
            # Automotive
            "Tires": [{"name": "Brand", "required": True}, {"name": "Size (e.g., 205/55R16)", "required": True}, {"name": "Condition", "required": True}],
            "Engine Oil": [{"name": "Brand", "required": True}, {"name": "Viscosity (e.g., 5W-30)", "required": True}, {"name": "Volume (Liters)", "required": True}],
            
            # Services (Categorized mapping)
            "Web Development": SERVICE_BASE + [{"name": "Tech Stack", "required": False}, {"name": "Includes Hosting (Yes/No)", "required": True}],
            "Graphic Design": SERVICE_BASE + [{"name": "Delivery Format (PNG/PSD/Vector)", "required": True}, {"name": "Number of Revisions", "required": True}],
            "Solar Setup": SERVICE_BASE + [{"name": "System Size Capacity (kVA)", "required": True}],
            "House Cleaning": SERVICE_BASE + [{"name": "Property Size (Rooms)", "required": True}, {"name": "Cleaning Type (Standard/Deep)", "required": True}]
        }

        updated_count = 0

        # 1. Apply Specific Schemas
        for category_name, schema in ATTRIBUTE_MAPPING.items():
            categories = Category.objects.filter(name=category_name)
            for category in categories:
                category.attribute_schema = schema
                category.save()
                updated_count += 1
                self.stdout.write(f"Updated specific schema for: {category_name}")

        # 2. Apply Universal Fallback to everything else
        unmapped_categories = Category.objects.filter(attribute_schema=[])
        fallback_count = unmapped_categories.count()
        
        for category in unmapped_categories:
            category.attribute_schema = UNIVERSAL_FALLBACK
            category.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully injected {updated_count} specific schemas.'))
        self.stdout.write(self.style.SUCCESS(f'Applied universal fallback schema to {fallback_count} remaining categories.'))