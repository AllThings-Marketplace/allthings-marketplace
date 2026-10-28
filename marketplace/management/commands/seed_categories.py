from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from marketplace.models import Category


PRODUCT_CATEGORIES = [
    {
        "name": "Cables, Wires & Conduits",
        "keywords": "wire, cable, coil, copper, aluminium, conduit, trunking, coleman, cutix, nigerchin, mm, armoured, earth",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Conductor Material", "required": True},
            {"name": "Length (Meters)", "required": False},
        ],
        "subcategories": [
            {
                "name": "House Wiring & Building Cables",
                "keywords": "single core, twin and earth, flat cable, 1.5mm, 2.5mm, 4mm, 6mm, 10mm, 16mm, coil, copper wire, pvc wire, coleman, cutix",
                "schema": [
                    {"name": "Cable Gauge (mm²)", "required": True},
                    {"name": "Core Type (Single / Twin & Earth)", "required": True},
                    {"name": "Coil Length (m)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Armoured & Underground Cables",
                "keywords": "armoured, swa, underground, 25mm, 35mm, 50mm, 70mm, 95mm, 4 core, 3 core, high tension, feeder pillar cable",
                "schema": [
                    {"name": "Cable Size (mm²)", "required": True},
                    {"name": "Number of Cores", "required": True},
                    {"name": "Conductor (Copper / Aluminium)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "Flexible Cords & Control Cables",
                "keywords": "flexible cable, flex, 3 core flex, appliance cord, extension wire, submersible cable, welding cable",
                "schema": [
                    {"name": "Core Count & Gauge", "required": True},
                    {"name": "Roll Length (m)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "PVC Conduits, Trunking & Accessories",
                "keywords": "conduit pipe, pvc pipe, trunking, adaptable box, circular box, coupler, saddle clip, bend, 20mm, 25mm, patress box",
                "schema": [
                    {"name": "Size / Diameter (mm)", "required": True},
                    {"name": "Material (PVC / Galvanized)", "required": True},
                    {"name": "Pack Quantity", "required": False},
                ],
            },
        ],
    },
    {
        "name": "Solar, Inverters & Power Backup",
        "keywords": "solar, inverter, battery, lithium, lifepo4, tubular, mppt, charge controller, panel, power station, kva, felicity, deye, luminous",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Warranty Period", "required": False},
        ],
        "subcategories": [
            {
                "name": "Hybrid & Pure Sine Wave Inverters",
                "keywords": "inverter, hybrid inverter, pure sine wave, kva, kw, 1.5kva, 3kva, 5kva, 8kva, 10kva, 12v, 24v, 48v, felicity, deye, growatt, luminous, kartel",
                "schema": [
                    {"name": "Rated Capacity (kVA / kW)", "required": True},
                    {"name": "System Battery Voltage (12V/24V/48V)", "required": True},
                    {"name": "Inverter Type (Hybrid / Non-Hybrid)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Solar Panels (Monocrystalline & Bifacial)",
                "keywords": "solar panel, monocrystalline, polycrystalline, bifacial, half cut, jinko, canadian solar, longi, trina, 200w, 300w, 450w, 550w, 600w",
                "schema": [
                    {"name": "Rated Power (Watts)", "required": True},
                    {"name": "Cell Type (Mono / Bifacial)", "required": True},
                    {"name": "Open Circuit Voltage (Voc)", "required": False},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Lithium (LiFePO4) & Tubular Batteries",
                "keywords": "battery, lithium battery, lifepo4, tubular battery, deep cycle, agm, gel, 200ah, 220ah, 5kwh, 10kwh, 15kwh, felicity, luminous, starplus, Eastman",
                "schema": [
                    {"name": "Capacity (Ah or kWh)", "required": True},
                    {"name": "Nominal Voltage (12V / 24V / 48V)", "required": True},
                    {"name": "Battery Chemistry (LiFePO4 / Tubular / Gel)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "MPPT & PWM Solar Charge Controllers",
                "keywords": "charge controller, mppt, pwm, 40a, 60a, 80a, 100a, fangpusun, felicity, powmr",
                "schema": [
                    {"name": "Max Current Rating (Amps)", "required": True},
                    {"name": "System Voltage (12V/24V/48V Auto)", "required": True},
                    {"name": "Controller Type (MPPT / PWM)", "required": True},
                ],
            },
        ],
    },
    {
        "name": "Circuit Protection & Switchgear",
        "keywords": "breaker, distribution board, db, mcb, mccb, rcd, elcb, changeover, ats, isolator, fuse, stabilizer, avr, surge protector, schneider, abb, havells",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Current / Power Rating", "required": True},
        ],
        "subcategories": [
            {
                "name": "Distribution Boards (DB) & Consumer Units",
                "keywords": "distribution board, db box, consumer unit, 4 way, 6 way, 8 way, 12 way, 16 way, single phase db, three phase tpn",
                "schema": [
                    {"name": "Number of Ways", "required": True},
                    {"name": "Phase Type (Single Phase / 3-Phase TPN)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Circuit Breakers (MCB, MCCB, RCD & ELCB)",
                "keywords": "mcb, mccb, rcd, elcb, circuit breaker, miniature breaker, 16a, 20a, 32a, 63a, 100a, 1p, 2p, 3p, 4p",
                "schema": [
                    {"name": "Amperage Rating (A)", "required": True},
                    {"name": "Number of Poles (1P / 2P / 3P / 4P)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Changeover Switches, ATS & Isolators",
                "keywords": "changeover, automatic transfer switch, ats, isolator, 63a, 100a, 200a, 400a, socomec",
                "schema": [
                    {"name": "Current Rating (Amps)", "required": True},
                    {"name": "Operation Mode (Manual / Automatic ATS)", "required": True},
                ],
            },
            {
                "name": "Voltage Stabilizers (AVR) & Surge Protectors",
                "keywords": "stabilizer, avr, voltage regulator, surge protector, tv guard, fridge guard, 5000va, 10kva, binatone, sollatek",
                "schema": [
                    {"name": "Capacity (VA / kVA)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
        ],
    },
    {
        "name": "Switches, Sockets & Accessories",
        "keywords": "switch, socket, wall switch, plug, extension box, dimmer, water heater switch, cooker unit, gang, 13a",
        "schema": [
            {"name": "Brand", "required": True},
            {"name": "Color / Finish", "required": False},
        ],
        "subcategories": [
            {
                "name": "Wall Switches & Dimmers",
                "keywords": "wall switch, 1 gang, 2 gang, 3 gang, 4 gang, 1 way, 2 way, dimmer",
                "schema": [
                    {"name": "Gang Count (1G / 2G / 3G / 4G)", "required": True},
                    {"name": "Switch Type (1-Way / 2-Way)", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Wall Sockets & Power Outlets",
                "keywords": "wall socket, 13a socket, double socket, single socket, usb socket, water heater switch",
                "schema": [
                    {"name": "Amperage Rating (13A / 15A / 45A)", "required": True},
                    {"name": "Gang Configuration", "required": True},
                    {"name": "Brand", "required": True},
                ],
            },
        ],
    },
    {
        "name": "Lighting & Smart Illumination",
        "keywords": "bulb, led, lighting, lamp, chandelier, pop light, downlight, panel light, floodlight, streetlight, akt, philips",
        "schema": [
            {"name": "Wattage (W)", "required": True},
            {"name": "Light Color (Warm / Cool / Daylight)", "required": False},
        ],
        "subcategories": [
            {
                "name": "LED Bulbs, Tubes & POP Downlights",
                "keywords": "led bulb, energy bulb, pop light, panel light, downlight, t8 tube, 9w, 12w, 18w, akt, vellmax",
                "schema": [
                    {"name": "Wattage (Watts)", "required": True},
                    {"name": "Fitting Type (E27 / B22 / Recessed)", "required": True},
                    {"name": "Brand", "required": False},
                ],
            },
            {
                "name": "Floodlights & Solar Security Lights",
                "keywords": "floodlight, solar street light, security light, 50w, 100w, 200w, ip65",
                "schema": [
                    {"name": "Power Rating (Watts)", "required": True},
                    {"name": "Weatherproof Rating (IP65 / IP66)", "required": False},
                ],
            },
        ],
    },
    {
        "name": "Electrical Tools & Testing Gear",
        "keywords": "tool, multimeter, clamp meter, tester, screwdriver, plier, crimping, stripper, sub meter, prepaid meter",
        "schema": [
            {"name": "Brand", "required": True},
        ],
        "subcategories": [
            {
                "name": "Multimeters & Clamp Meters",
                "keywords": "multimeter, digital multimeter, clamp meter, voltage detector, uni-t, fluke",
                "schema": [
                    {"name": "Brand", "required": True},
                ],
            },
            {
                "name": "Electrician Hand & Power Tools",
                "keywords": "drill, cordless drill, crimping tool, cable cutter, wire stripper, pliers, ingco, total",
                "schema": [
                    {"name": "Brand", "required": True},
                ],
            },
        ],
    },
]


SERVICE_CATEGORIES = [
    {
        "name": "Solar & Inverter Engineering Services",
        "keywords": "solar installation, inverter installation, inverter repair, battery installation, solar maintenance",
        "subcategories": [
            {"name": "Complete Solar & Inverter System Installation", "keywords": "solar installation, inverter setup, roof mounting"},
            {"name": "Inverter & Charge Controller Fault Repair", "keywords": "inverter repair, board repair, overload fault"},
            {"name": "Solar Panel Cleaning & System Upgrade", "keywords": "solar cleaning, panel relocation, array upgrade"},
        ],
    },
    {
        "name": "Residential & Commercial Electrical Wiring",
        "keywords": "house wiring, conduit wiring, electrician, db dressing, changeover installation, fault tracing",
        "subcategories": [
            {"name": "Full Building Conduit & Surface Wiring", "keywords": "house wiring, conduit piping, surface wiring"},
            {"name": "Distribution Board (DB) Upgrade & Balancing", "keywords": "distribution board, db dressing, load balancing, breaker replacement"},
            {"name": "Changeover, ATS & Generator Integration", "keywords": "changeover installation, automatic transfer switch, ats wiring"},
            {"name": "Electrical Fault Tracing & Emergency Repair", "keywords": "fault tracing, power outage, tripping breaker, short circuit"},
        ],
    },
    {
        "name": "Lighting & Security Systems Setup",
        "keywords": "chandelier installation, pop lighting, cctv installation, smart switch, electric fence",
        "subcategories": [
            {"name": "Chandelier & POP Downlight Installation", "keywords": "chandelier mounting, pop light installation, led strip"},
            {"name": "CCTV Camera & Access Control Setup", "keywords": "cctv installation, ip camera, electric fence"},
        ],
    },
    {
        "name": "HVAC & Appliance Engineering",
        "keywords": "ac installation, ac repair, gas refill, air conditioner servicing, water heater installation",
        "subcategories": [
            {"name": "Split & Standing AC Installation & Relocation", "keywords": "ac installation, split ac mounting, copper piping"},
            {"name": "AC Servicing & Gas Charging", "keywords": "ac servicing, gas refill, compressor repair"},
        ],
    },
]


class Command(BaseCommand):
    help = "Seeds structured electrical product and technical service categories."

    def _unique_slug(self, base_text, prefix=""):
        raw = f"{prefix}-{base_text}" if prefix else base_text
        return slugify(raw)[:95]

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding Electrical Product Categories ==="))
        for parent_data in PRODUCT_CATEGORIES:
            parent_slug = self._unique_slug(parent_data["name"], "prod")
            parent_cat, created = Category.objects.update_or_create(
                name=parent_data["name"],
                parent=None,
                defaults={
                    "slug": parent_slug,
                    "category_type": "PRODUCT",
                    "search_keywords": parent_data["keywords"],
                    "attribute_schema": parent_data.get("schema", []),
                    "is_active": True,
                },
            )
            created_count += int(created)
            updated_count += int(not created)
            self.stdout.write(f"  [PRODUCT] {parent_cat.name}")

            for sub_data in parent_data.get("subcategories", []):
                sub_slug = self._unique_slug(sub_data["name"], "prod")
                sub_cat, sub_created = Category.objects.update_or_create(
                    name=sub_data["name"],
                    parent=parent_cat,
                    defaults={
                        "slug": sub_slug,
                        "category_type": "PRODUCT",
                        "search_keywords": sub_data["keywords"],
                        "attribute_schema": sub_data.get("schema", []),
                        "is_active": True,
                    },
                )
                created_count += int(sub_created)
                updated_count += int(not sub_created)
                self.stdout.write(f"     └── {sub_cat.name}")

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding Technical Service Categories ==="))
        for parent_data in SERVICE_CATEGORIES:
            parent_slug = self._unique_slug(parent_data["name"], "srv")
            parent_cat, created = Category.objects.update_or_create(
                name=parent_data["name"],
                parent=None,
                defaults={
                    "slug": parent_slug,
                    "category_type": "SERVICE",
                    "search_keywords": parent_data["keywords"],
                    "attribute_schema": [],
                    "is_active": True,
                },
            )
            created_count += int(created)
            updated_count += int(not created)
            self.stdout.write(f"  [SERVICE] {parent_cat.name}")

            for sub_data in parent_data.get("subcategories", []):
                sub_slug = self._unique_slug(sub_data["name"], "srv")
                sub_cat, sub_created = Category.objects.update_or_create(
                    name=sub_data["name"],
                    parent=parent_cat,
                    defaults={
                        "slug": sub_slug,
                        "category_type": "SERVICE",
                        "search_keywords": sub_data["keywords"],
                        "attribute_schema": [],
                        "is_active": True,
                    },
                )
                created_count += int(sub_created)
                updated_count += int(not sub_created)
                self.stdout.write(f"     └── {sub_cat.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Created {created_count} new categories and updated {updated_count} existing categories."
            )
        )