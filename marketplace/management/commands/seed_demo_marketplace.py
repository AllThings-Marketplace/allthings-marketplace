import io
from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import ProviderProfile, VendorWallet
from marketplace.models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    Service,
    ServicePackage,
    PromoBanner,
    CustomerRequest,
    RequestMatch,
)

User = get_user_model()


def _generate_placeholder_image(label, bg_hex="#1e3a8a", accent_hex="#f97316", size=(800, 600)):
    """
    Generates a clean in-memory JPEG image using Pillow so demo banners,
    products, and services render with crisp visuals immediately.
    """
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", size, color=bg_hex)
        draw = ImageDraw.Draw(img)

        # Decorative accent bar at the bottom
        bar_height = max(16, int(size[1] * 0.06))
        draw.rectangle(
            [(0, size[1] - bar_height), (size[0], size[1])],
            fill=accent_hex,
        )

        # Subtle border frame
        draw.rectangle(
            [(20, 20), (size[0] - 20, size[1] - bar_height - 20)],
            outline="#3b82f6",
            width=2,
        )

        # Center label text
        short_label = (label or "AllThings")[:36]
        text_x = max(40, (size[0] - (len(short_label) * 8)) // 2)
        text_y = size[1] // 2 - 10
        draw.text((text_x, text_y), short_label, fill="#ffffff")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return ContentFile(buffer.getvalue())
    except Exception:
        return None


class Command(BaseCommand):
    help = "Populates demo verified providers, approved electrical products, technical services, banners, and buyer requests."

    def _get_category(self, keyword, cat_type="PRODUCT"):
        cat = Category.objects.filter(
            name__icontains=keyword,
            category_type=cat_type,
            is_active=True,
        ).first()
        if not cat:
            cat = Category.objects.filter(
                category_type=cat_type,
                parent__isnull=False,
                is_active=True,
            ).first()
        if not cat:
            cat = Category.objects.filter(category_type=cat_type, is_active=True).first()
        return cat

    def _create_provider(self, username, email, first_name, last_name, biz_name, prov_type, region, address, category_label):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        if created:
            user.set_password("AllThings2026!")
            user.save()

        allowed_fields = {f.name for f in ProviderProfile._meta.get_fields()}
        raw_defaults = {
            "business_name": biz_name,
            "provider_type": prov_type,
            "verification_status": "ACTIVE",
            "trust_score": 96,
            "business_category": category_label,
            "business_description": (
                f"{biz_name} is a KYC-verified AllThings partner supplying genuine electrical "
                f"hardware and certified engineering support across {region}."
            ),
            "phone": "+2348030001122",
            "region": region,
            "store_address": address,
            "latitude": 4.8156,
            "longitude": 7.0498,
            "bank_name": "Guaranty Trust Bank (GTB)",
            "bank_code": "058",
            "account_number": "0123456789",
            "account_name": biz_name,
            "email_verified": True,
        }
        filtered_defaults = {k: v for k, v in raw_defaults.items() if k in allowed_fields}

        profile, _ = ProviderProfile.objects.update_or_create(
            user=user,
            defaults=filtered_defaults,
        )
        VendorWallet.objects.get_or_create(
            provider=profile,
            defaults={
                "available_balance": Decimal("185000.00"),
                "pending_balance": Decimal("65000.00"),
                "total_withdrawn": Decimal("420000.00"),
            },
        )
        return profile

    @transaction.atomic
    def handle(self, *args, **options):
        if not Category.objects.exists():
            self.stdout.write("No categories found. Running seed_categories first...")
            call_command("seed_categories")

        self.stdout.write(self.style.MIGRATE_HEADING("=== 1. Creating Demo Buyer & Verified Providers ==="))

        # Demo Customer Account
        buyer, created = User.objects.get_or_create(
            username="demo_buyer",
            defaults={
                "email": "buyer@allthings.com",
                "first_name": "Chidi",
                "last_name": "Okafor",
            },
        )
        if created:
            buyer.set_password("AllThings2026!")
            buyer.save()

        # 3 Verified Providers (VENDOR, SERVICE, BOTH)
        solar_hub = self._create_provider(
            username="volt_edge_solar",
            email="voltedge@allthings.com",
            first_name="Emeka",
            last_name="Nwosu",
            biz_name="VoltEdge Solar & Power Systems",
            prov_type="BOTH",
            region="Rivers State",
            address="Plot 42 Aba Road, By Garrison Junction, Port Harcourt",
            category_label="Solar & Inverter Systems",
        )

        cable_depot = self._create_provider(
            username="ph_cable_depot",
            email="cables@allthings.com",
            first_name="Tunde",
            last_name="Adeyemi",
            biz_name="PrimeWire & Switchgear Depot",
            prov_type="VENDOR",
            region="Rivers State",
            address="18 Old Aba Road, Oyigbo, Rivers State",
            category_label="Cables, Switchgear & Lighting",
        )

        apex_eng = self._create_provider(
            username="apex_grid_engineers",
            email="apex@allthings.com",
            first_name="Ibrahim",
            last_name="Danjuma",
            biz_name="ApexGrid Certified Electrical Services",
            prov_type="SERVICE",
            region="Rivers State",
            address="24 Stadium Road, Elekahia, Port Harcourt",
            category_label="Electrical Wiring & HVAC Engineering",
        )

        self.stdout.write(self.style.SUCCESS("  ✓ Created demo_buyer and 3 ACTIVE providers (Password: AllThings2026!)"))

        # 2. Seed Promo Banners
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 2. Seeding Homepage Promo Banners ==="))
        banner_specs = [
            {
                "title": "100% Escrow-Protected Solar & Electrical Hardware",
                "subtitle": "Shop genuine inverters, lithium batteries, and copper cables with live dispatch rates.",
                "link": "/?item_type=products",
                "order": 1,
                "bg": "#0f172a",
            },
            {
                "title": "Hire KYC-Verified Electrical & Solar Engineers",
                "subtitle": "Book certified technicians across Rivers State with milestone escrow protection.",
                "link": "/?item_type=services",
                "order": 2,
                "bg": "#1e3a8a",
            },
        ]
        for b_data in banner_specs:
            banner, b_created = PromoBanner.objects.get_or_create(
                title=b_data["title"],
                defaults={
                    "subtitle": b_data["subtitle"],
                    "link": b_data["link"],
                    "display_order": b_data["order"],
                    "is_active": True,
                },
            )
            if b_created and not banner.image:
                img_content = _generate_placeholder_image(b_data["title"], bg_hex=b_data["bg"], size=(1600, 520))
                if img_content:
                    banner.image.save(f"banner_{b_data['order']}.jpg", img_content, save=True)

        # 3. Seed Approved Electrical Products Across Departments
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 3. Seeding Approved Electrical Products ==="))
        product_catalog = [
            {
                "provider": solar_hub,
                "cat_key": "Hybrid & Pure Sine Wave Inverters",
                "name": "Felicity 5kVA 48V Hybrid Pure Sine Wave Inverter (Built-in 100A MPPT)",
                "price": Decimal("685000.00"),
                "stock": 8,
                "shipping_class": Product.ShippingClass.HEAVY,
                "weight_kg": Decimal("24.50"),
                "description": (
                    "Original Felicity Solar 5kVA 48V Pure Sine Wave Hybrid Inverter featuring a built-in "
                    "100A MPPT solar charge controller, high PV input range (120V-450V DC), Wi-Fi monitoring support, "
                    "and lithium battery BMS communication."
                ),
                "attributes": {
                    "Rated Capacity (kVA / kW)": "5kVA / 5000W",
                    "System Battery Voltage (12V/24V/48V)": "48V DC",
                    "Inverter Type (Hybrid / Non-Hybrid)": "Hybrid (Solar + Grid + Battery)",
                    "Brand": "Felicity Solar",
                },
                "variants": [],
            },
            {
                "provider": solar_hub,
                "cat_key": "Lithium (LiFePO4) & Tubular Batteries",
                "name": "Felicity 10kWh 48V 200Ah LiFePO4 Wall-Mounted Lithium Battery",
                "price": Decimal("1650000.00"),
                "stock": 5,
                "shipping_class": Product.ShippingClass.HEAVY,
                "weight_kg": Decimal("78.00"),
                "description": (
                    "Deep-cycle 10kWh 48V 200Ah Lithium Iron Phosphate (LiFePO4) battery pack with smart BMS, "
                    "6000+ life cycles at 80% DOD, LCD status display, and 5-year manufacturer warranty."
                ),
                "attributes": {
                    "Capacity (Ah or kWh)": "10kWh (200Ah)",
                    "Nominal Voltage (12V / 24V / 48V)": "48V",
                    "Battery Chemistry (LiFePO4 / Tubular / Gel)": "LiFePO4 Lithium",
                    "Brand": "Felicity Solar",
                },
                "variants": [],
            },
            {
                "provider": solar_hub,
                "cat_key": "Solar Panels",
                "name": "Jinko Tiger Neo 550W Monocrystalline Half-Cell Solar Panel",
                "price": Decimal("142000.00"),
                "stock": 30,
                "shipping_class": Product.ShippingClass.HEAVY,
                "weight_kg": Decimal("26.50"),
                "description": (
                    "Grade-A Jinko 550W N-Type Monocrystalline solar module with high low-light efficiency, "
                    "anodized aluminum alloy frame, and IP68 junction box."
                ),
                "attributes": {
                    "Rated Power (Watts)": "550W",
                    "Cell Type (Mono / Bifacial)": "Monocrystalline Half-Cut",
                    "Brand": "Jinko Solar",
                },
                "variants": [],
            },
            {
                "provider": solar_hub,
                "cat_key": "MPPT & PWM Solar Charge Controllers",
                "name": "PowMr 60A MPPT Solar Charge Controller (12V/24V/36V/48V Auto)",
                "price": Decimal("95000.00"),
                "stock": 14,
                "shipping_class": Product.ShippingClass.SMALL,
                "weight_kg": Decimal("2.20"),
                "description": (
                    "Intelligent 60A MPPT solar controller supporting lead-acid, gel, tubular, and lithium batteries "
                    "with max PV input up to 160V DC."
                ),
                "attributes": {
                    "Max Current Rating (Amps)": "60A",
                    "System Voltage (12V/24V/48V Auto)": "12V/24V/36V/48V Auto",
                    "Controller Type (MPPT / PWM)": "MPPT",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "House Wiring & Building Cables",
                "name": "Coleman 2.5mm² Single Core Pure Copper PVC Building Wire (100m Coil)",
                "price": Decimal("68000.00"),
                "stock": 40,
                "shipping_class": Product.ShippingClass.MEDIUM,
                "weight_kg": Decimal("6.50"),
                "description": (
                    "SON-certified Coleman 2.5mm² single-core 100% copper PVC-insulated house wiring coil (100 meters). "
                    "Ideal for 13A ring mains, sockets, and residential conduit installations."
                ),
                "attributes": {
                    "Cable Gauge (mm²)": "2.5mm²",
                    "Core Type (Single / Twin & Earth)": "Single Core",
                    "Coil Length (m)": "100m",
                    "Brand": "Coleman Wires & Cables",
                },
                "variants": [
                    ("Insulation Color", "Red (Live)", Decimal("68000.00"), 15),
                    ("Insulation Color", "Black (Neutral)", Decimal("68000.00"), 15),
                    ("Insulation Color", "Green/Yellow (Earth)", Decimal("68000.00"), 10),
                ],
            },
            {
                "provider": cable_depot,
                "cat_key": "Armoured & Underground Cables",
                "name": "Coleman 16mm² 4-Core Copper SWA Armoured Underground Cable (Per Meter)",
                "price": Decimal("18500.00"),
                "stock": 120,
                "shipping_class": Product.ShippingClass.HEAVY,
                "weight_kg": Decimal("3.40"),
                "description": (
                    "Heavy-duty 16mm² 4-core Steel Wire Armoured (SWA) pure copper underground power cable for "
                    "3-phase generator hookups, main incomers, and sub-main distribution."
                ),
                "attributes": {
                    "Cable Size (mm²)": "16mm²",
                    "Number of Cores": "4-Core",
                    "Conductor (Copper / Aluminium)": "Pure Copper",
                    "Brand": "Coleman",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "Distribution Boards (DB) & Consumer Units",
                "name": "Schneider Electric 12-Way Single Phase Flush Distribution Board (With 100A Isolator)",
                "price": Decimal("74000.00"),
                "stock": 12,
                "shipping_class": Product.ShippingClass.MEDIUM,
                "weight_kg": Decimal("5.80"),
                "description": (
                    "Original Schneider Electric 12-way metal flush consumer unit complete with 100A main incomer "
                    "isolator, neutral/earth busbars, and full DIN rail kit."
                ),
                "attributes": {
                    "Number of Ways": "12-Way",
                    "Phase Type (Single Phase / 3-Phase TPN)": "Single Phase",
                    "Brand": "Schneider Electric",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "Changeover Switches, ATS & Isolators",
                "name": "ABB 100A 4-Pole Automatic Transfer Switch (ATS) for Generator & PHCN",
                "price": Decimal("135000.00"),
                "stock": 9,
                "shipping_class": Product.ShippingClass.MEDIUM,
                "weight_kg": Decimal("4.50"),
                "description": (
                    "Zero-delay 100A 4-pole Automatic Transfer Switch (ATS) with manual override handle for seamless "
                    "switching between utility grid, generator, and inverter output."
                ),
                "attributes": {
                    "Current Rating (Amps)": "100A",
                    "Operation Mode (Manual / Automatic ATS)": "Automatic ATS + Manual Mode",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "Wall Sockets",
                "name": "Schneider Lisse 13A Double Switched Wall Socket with Dual USB Ports (White)",
                "price": Decimal("14500.00"),
                "stock": 55,
                "shipping_class": Product.ShippingClass.SMALL,
                "weight_kg": Decimal("0.40"),
                "description": (
                    "Sleek British-standard 13A 2-gang switched wall socket featuring integrated Type-A and Type-C "
                    "fast-charge USB ports and child-safe shuttered outlets."
                ),
                "attributes": {
                    "Amperage Rating (13A / 15A / 45A)": "13A + 2.4A USB",
                    "Gang Configuration": "Double (2-Gang)",
                    "Brand": "Schneider Electric",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "Floodlights",
                "name": "200W IP66 All-in-One Solar Floodlight with Remote & Dusk-to-Dawn Sensor",
                "price": Decimal("48000.00"),
                "stock": 25,
                "shipping_class": Product.ShippingClass.MEDIUM,
                "weight_kg": Decimal("5.20"),
                "description": (
                    "High-lumen 200W outdoor solar security floodlight with polycrystalline solar panel, LiFePO4 battery "
                    "pack, 5m waterproof cable, and wireless timer remote."
                ),
                "attributes": {
                    "Power Rating (Watts)": "200W",
                    "Weatherproof Rating (IP65 / IP66)": "IP66 Weatherproof",
                },
                "variants": [],
            },
            {
                "provider": cable_depot,
                "cat_key": "Multimeters",
                "name": "UNI-T UT204+ True RMS Digital AC/DC Clamp Meter (600A / 600V)",
                "price": Decimal("38500.00"),
                "stock": 18,
                "shipping_class": Product.ShippingClass.SMALL,
                "weight_kg": Decimal("0.65"),
                "description": (
                    "Professional True-RMS digital clamp meter measuring both AC and DC current up to 600A—essential "
                    "for solar battery bank diagnostics, inverter load audits, and fault tracing."
                ),
                "attributes": {
                    "Brand": "UNI-T",
                },
                "variants": [],
            },
        ]

        created_products = []
        for idx, p_data in enumerate(product_catalog, start=1):
            cat = self._get_category(p_data["cat_key"], "PRODUCT")
            product, p_created = Product.objects.update_or_create(
                name=p_data["name"],
                provider=p_data["provider"],
                defaults={
                    "category": cat,
                    "price": p_data["price"],
                    "stock_count": p_data["stock"],
                    "shipping_class": p_data["shipping_class"],
                    "weight_kg": p_data["weight_kg"],
                    "description": p_data["description"],
                    "attributes": p_data["attributes"],
                    "status": Product.ProductStatus.APPROVED,
                    "is_active": True,
                },
            )
            if not product.image:
                img_file = _generate_placeholder_image(product.name, bg_hex="#1e293b", accent_hex="#2563eb")
                if img_file:
                    product.image.save(f"prod_{idx}.jpg", img_file, save=True)
                    ProductImage.objects.get_or_create(
                        product=product,
                        image_type="MAIN",
                        defaults={
                            "original_image": product.image,
                            "processed_image": product.image,
                            "thumbnail": product.image,
                            "processing_status": "APPROVED",
                            "is_approved": True,
                        },
                    )

            for attr_name, attr_val, v_price, v_stock in p_data["variants"]:
                ProductVariant.objects.update_or_create(
                    product=product,
                    attribute_name=attr_name,
                    attribute_value=attr_val,
                    defaults={"price_override": v_price, "stock": v_stock},
                )
            created_products.append(product)
            self.stdout.write(f"  [PRODUCT] {product.name} — NGN {product.price:,.0f}")

        # 4. Seed Certified Professional Technical Services
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 4. Seeding Certified Professional Services ==="))
        service_catalog = [
            {
                "provider": solar_hub,
                "cat_key": "Complete Solar & Inverter System Installation",
                "name": "Complete 5kVA–10kVA Hybrid Solar & Lithium Battery System Installation",
                "mode": Service.ServiceMode.CUSTOMER_LOC,
                "radius": 50,
                "pricing_type": Service.PricingType.PACKAGES,
                "base_price": Decimal("85000.00"),
                "description": (
                    "End-to-end engineering installation of hybrid inverters, rooftop solar arrays, AC/DC combiner "
                    "boxes, surge arrestors, and DB sub-circuit separation for homes and offices in Rivers State."
                ),
                "included": [
                    "Full appliance load audit & DB separation",
                    "Roof rail mounting & PV string wiring",
                    "AC/DC surge protection & breaker dressing",
                    "System commissioning & client training",
                ],
                "excluded": [
                    "Inverter, battery, or panel hardware cost (unless purchased from our store)",
                    "Civil concrete plinth work",
                ],
                "packages": [
                    ("Basic (1.5kVA – 3.5kVA Setup)", "Inverter + battery bank + up to 4 solar panels", Decimal("85000.00"), "1 Day"),
                    ("Standard (5kVA Hybrid Setup)", "5kVA inverter + lithium battery + up to 8 panels + DB split", Decimal("135000.00"), "1–2 Days"),
                    ("Premium (8kVA – 15kVA 3-Phase)", "Commercial/Duplex hybrid array + full earthing & surge kit", Decimal("220000.00"), "2–3 Days"),
                ],
            },
            {
                "provider": apex_eng,
                "cat_key": "Full Building Conduit & Surface Wiring",
                "name": "Full Residential & Commercial Building Conduit Electrical Wiring",
                "mode": Service.ServiceMode.CUSTOMER_LOC,
                "radius": 60,
                "pricing_type": Service.PricingType.STARTING,
                "base_price": Decimal("120000.00"),
                "description": (
                    "COREN/NEMSA-compliant first-fix and second-fix conduit electrical wiring for flats, duplexes, "
                    "and commercial plazas, including distribution board termination and earth rod installation."
                ),
                "included": [
                    "Conduit piping & patress box installation",
                    "Cable drawing & circuit labeling",
                    "DB dressing & phase balancing",
                    "Insulation resistance & continuity testing",
                ],
                "excluded": [
                    "Cables, switches, and DB materials",
                ],
                "packages": [],
            },
            {
                "provider": apex_eng,
                "cat_key": "Electrical Fault Tracing",
                "name": "Emergency Electrical Fault Tracing, Tripping Breaker & Short-Circuit Repair",
                "mode": Service.ServiceMode.CUSTOMER_LOC,
                "radius": 35,
                "pricing_type": Service.PricingType.FIXED,
                "base_price": Decimal("25000.00"),
                "description": (
                    "Rapid diagnostic response for tripping RCD/MCB breakers, burnt distribution boards, earth leakage "
                    "shocks, phase loss, and high prepaid meter consumption in Port Harcourt and Oyigbo."
                ),
                "included": [
                    "Digital clamp-meter & insulation diagnostics",
                    "Fault isolation & burnt terminal re-termination",
                    "Load balancing across phases",
                ],
                "excluded": [
                    "Replacement breakers or new cable coils",
                ],
                "packages": [],
            },
            {
                "provider": apex_eng,
                "cat_key": "Changeover, ATS & Generator Integration",
                "name": "Automatic Transfer Switch (ATS) & 3-Phase Changeover Installation",
                "mode": Service.ServiceMode.CUSTOMER_LOC,
                "radius": 45,
                "pricing_type": Service.PricingType.FIXED,
                "base_price": Decimal("35000.00"),
                "description": (
                    "Professional installation of manual gear switches or automatic transfer switches (ATS) with "
                    "generator auto-stop integration and phase failure protection."
                ),
                "included": [
                    "Wall mounting & armoured cable gland termination",
                    "Generator signal relay connection",
                    "Live changeover testing under load",
                ],
                "excluded": [
                    "ATS box and armoured cable length",
                ],
                "packages": [],
            },
            {
                "provider": apex_eng,
                "cat_key": "Split & Standing AC Installation",
                "name": "Split & Standing Air Conditioner Installation, Gas Charging & Servicing",
                "mode": Service.ServiceMode.CUSTOMER_LOC,
                "radius": 40,
                "pricing_type": Service.PricingType.FIXED,
                "base_price": Decimal("20000.00"),
                "description": (
                    "Complete indoor/outdoor unit mounting, vacuum pressure testing, R410A/R32 refrigerant top-up, "
                    "and dedicated 20A water-heater/AC control switch wiring."
                ),
                "included": [
                    "Indoor & outdoor bracket installation",
                    "Copper flaring & leak test",
                    "Drain pipe routing & test run",
                ],
                "excluded": [
                    "Extra copper pipe beyond factory kit",
                ],
                "packages": [],
            },
        ]

        created_services = []
        for idx, s_data in enumerate(service_catalog, start=1):
            cat = self._get_category(s_data["cat_key"], "SERVICE")
            service, _ = Service.objects.update_or_create(
                name=s_data["name"],
                provider=s_data["provider"],
                defaults={
                    "category": cat,
                    "description": s_data["description"],
                    "service_mode": s_data["mode"],
                    "service_radius_km": s_data["radius"],
                    "pricing_type": s_data["pricing_type"],
                    "base_price": s_data["base_price"],
                    "whats_included": s_data["included"],
                    "whats_excluded": s_data["excluded"],
                    "status": Service.ServiceStatus.APPROVED,
                    "is_active": True,
                },
            )
            if not service.cover_image:
                srv_img = _generate_placeholder_image(service.name, bg_hex="#0f172a", accent_hex="#10b981")
                if srv_img:
                    service.cover_image.save(f"srv_{idx}.jpg", srv_img, save=True)

            for pkg_name, pkg_desc, pkg_price, pkg_dur in s_data["packages"]:
                ServicePackage.objects.update_or_create(
                    service=service,
                    name=pkg_name,
                    defaults={
                        "description": pkg_desc,
                        "price": pkg_price,
                        "estimated_duration": pkg_dur,
                        "features": s_data["included"],
                    },
                )
            created_services.append(service)
            self.stdout.write(f"  [SERVICE] {service.name}")

        # 5. Seed Sample "Request What You Need" Buyer Requests
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 5. Seeding Sample Buyer Requests ('Request What You Need') ==="))
        inv_cat = self._get_category("Hybrid & Pure Sine Wave Inverters", "PRODUCT")
        cable_cat = self._get_category("Armoured & Underground Cables", "PRODUCT")
        wiring_cat = self._get_category("Electrical Fault Tracing", "SERVICE")

        req1, _ = CustomerRequest.objects.get_or_create(
            customer=buyer,
            title="5kVA 48V Hybrid Solar Inverter with Wi-Fi Dongle",
            defaults={
                "request_type": CustomerRequest.RequestType.PRODUCT,
                "category": inv_cat,
                "brand": "Felicity or Deye",
                "specifications": "5kVA 48V, built-in 100A MPPT",
                "condition": CustomerRequest.ProductCondition.NEW,
                "budget_min": Decimal("600000.00"),
                "budget_max": Decimal("720000.00"),
                "region": "Rivers State",
                "location_detail": "GRA Phase 2, Port Harcourt",
                "description": "Looking for a brand new 5kVA 48V hybrid inverter ready for pickup or dispatch in Port Harcourt.",
                "status": CustomerRequest.RequestStatus.MATCHED,
            },
        )
        if created_products:
            RequestMatch.objects.get_or_create(
                customer_request=req1,
                product=created_products[0],
                defaults={
                    "provider": solar_hub,
                    "match_source": RequestMatch.MatchSource.SYSTEM,
                    "quoted_price": created_products[0].price,
                    "note": "Instant catalog match available in stock in Port Harcourt.",
                },
            )

        CustomerRequest.objects.get_or_create(
            customer=buyer,
            title="35 meters of 16mm 4-Core Armoured Copper Cable",
            defaults={
                "request_type": CustomerRequest.RequestType.PRODUCT,
                "category": cable_cat,
                "brand": "Coleman or Cutix",
                "specifications": "16mm² 4-Core SWA Pure Copper",
                "condition": CustomerRequest.ProductCondition.NEW,
                "budget_min": Decimal("550000.00"),
                "budget_max": Decimal("660000.00"),
                "region": "Rivers State",
                "location_detail": "Oyigbo",
                "description": "Need 35 meters cut length for a 30kVA generator installation in Oyigbo.",
                "status": CustomerRequest.RequestStatus.MATCHING,
            },
        )

        CustomerRequest.objects.get_or_create(
            customer=buyer,
            title="Certified Electrician for 3-Phase DB Load Balancing & ATS Setup",
            defaults={
                "request_type": CustomerRequest.RequestType.SERVICE,
                "category": wiring_cat,
                "specifications": "12-Way TPN DB + 100A ATS hookup",
                "budget_min": Decimal("30000.00"),
                "budget_max": Decimal("50000.00"),
                "region": "Rivers State",
                "location_detail": "Eliozu, Port Harcourt",
                "preferred_date": timezone.now().date(),
                "description": "One phase keeps tripping whenever the borehole pump and AC start together. Need load balancing.",
                "status": CustomerRequest.RequestStatus.MATCHING,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDemo marketplace seeded! {len(created_products)} products, "
                f"{len(created_services)} services, 2 promo banners, and 3 buyer requests are live."
            )
        )