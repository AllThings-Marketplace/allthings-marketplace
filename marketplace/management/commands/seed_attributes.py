from django.core.management.base import BaseCommand
from marketplace.models import Category

class Command(BaseCommand):
    help = 'Bulk updates existing electrical categories with dynamic JSON attribute schemas'

    def handle(self, *args, **kwargs):
        self.stdout.write("Injecting electrical category attributes...")

        ELECTRICAL_BASE = [
            {"name": "Brand", "required": True},
            {"name": "Condition (New/Refurbished)", "required": True},
            {"name": "Warranty Period", "required": False}
        ]
        SERVICE_BASE = [
            {"name": "Service Mode (On-site / Remote)", "required": True},
            {"name": "Estimated Duration", "required": True},
        ]
        UNIVERSAL_FALLBACK = [
            {"name": "Brand/Manufacturer", "required": False},
            {"name": "Condition", "required": False}
        ]

        ATTRIBUTE_MAPPING = {
            "House Wiring & Building Cables": ELECTRICAL_BASE + [{"name": "Cable Gauge (mm²)", "required": True}, {"name": "Coil Length (m)", "required": True}],
            "Armoured & Underground Cables": ELECTRICAL_BASE + [{"name": "Cable Size (mm²)", "required": True}, {"name": "Number of Cores", "required": True}],
            "Hybrid & Pure Sine Wave Inverters": ELECTRICAL_BASE + [{"name": "Capacity (kVA / kW)", "required": True}, {"name": "System Voltage (12V/24V/48V)", "required": True}],
            "Solar Panels (Monocrystalline & Bifacial)": ELECTRICAL_BASE + [{"name": "Rated Power (Watts)", "required": True}, {"name": "Cell Type", "required": True}],
            "Lithium (LiFePO4) & Tubular Batteries": ELECTRICAL_BASE + [{"name": "Capacity (Ah or kWh)", "required": True}, {"name": "Nominal Voltage", "required": True}],
            "Circuit Breakers (MCB, MCCB, RCD & ELCB)": ELECTRICAL_BASE + [{"name": "Amperage Rating (A)", "required": True}, {"name": "Poles (1P/2P/3P/4P)", "required": True}],
            "Complete Solar & Inverter System Installation": SERVICE_BASE + [{"name": "System Capacity (kVA)", "required": True}],
            "Full Building Conduit & Surface Wiring": SERVICE_BASE + [{"name": "Property Type (Residential/Commercial)", "required": True}],
        }

        updated_count = 0
        for category_name, schema in ATTRIBUTE_MAPPING.items():
            categories = Category.objects.filter(name=category_name)
            for category in categories:
                category.attribute_schema = schema
                category.save()
                updated_count += 1
                self.stdout.write(f"Updated specific schema for: {category_name}")

        unmapped_categories = Category.objects.filter(attribute_schema=[])
        fallback_count = unmapped_categories.count()
        for category in unmapped_categories:
            category.attribute_schema = UNIVERSAL_FALLBACK
            category.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully injected {updated_count} specific schemas and {fallback_count} fallbacks.'))