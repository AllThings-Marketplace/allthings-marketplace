from decimal import Decimal
from collections import defaultdict
from django.core import signing

# South-South / South-East neighboring states for regional rate calculation
REGIONAL_NEIGHBORS = {
    'rivers': {'bayelsa', 'abia', 'imo', 'akwa ibom', 'delta', 'edo', 'cross river', 'anambra'},
    'lagos': {'ogun', 'oyo', 'osun', 'ondo'},
    'abuja': {'niger', 'nasarawa', 'kogi', 'kaduna'},
}


def normalize_location(text):
    """Normalizes state/city names for reliable route matching."""
    if not text:
        return ''
    cleaned = text.strip().lower()
    for suffix in [' state', ' lga', ' municipal', ' metro']:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
    if cleaned in ['ph', 'phc', 'port-harcourt']:
        return 'port harcourt'
    if cleaned in ['fct', 'abuja fct']:
        return 'abuja'
    return cleaned


def classify_route(origin_state, origin_city, dest_state, dest_city):
    """
    Classifies a shipment leg into:
    - 'INTRA_CITY': Same State & Same City/LGA (e.g., PH to PH, or Oyigbo to Oyigbo)
    - 'INTRA_STATE': Same State, different LGA/town (e.g., PH to Oyigbo / Choba / Bonny)
    - 'REGIONAL': Neighboring states (e.g., Rivers to Abia / Bayelsa / Imo)
    - 'INTER_STATE': Long-haul interstate (e.g., Lagos or Abuja to Rivers)
    """
    o_state = normalize_location(origin_state) or 'rivers'
    d_state = normalize_location(dest_state) or 'rivers'
    o_city = normalize_location(origin_city)
    d_city = normalize_location(dest_city)

    if o_state == d_state:
        if o_city and d_city and o_city == d_city:
            return 'INTRA_CITY'
        # If destination city is inside the core metro area and vendor didn't specify a different town
        if not o_city and d_city in ['port harcourt', 'obio/akpor', 'obio akpor', 'oyigbo', 'elelenwo', 'choba']:
            return 'INTRA_STATE'
        return 'INTRA_STATE'

    neighbors = REGIONAL_NEIGHBORS.get(o_state, set())
    if d_state in neighbors or o_state in REGIONAL_NEIGHBORS.get(d_state, set()):
        return 'REGIONAL'

    return 'INTER_STATE'


class LogisticsEngine:
    """
    Multi-Vendor Shipping Quote & Verification Engine.
    Groups cart items by vendor pickup location, evaluates courier adapters,
    and cryptographically signs quotes so the frontend cannot tamper with fees.
    """
    SIGNING_SALT = 'allthings.logistics.quote.v1'
    QUOTE_MAX_AGE_SECONDS = 3600  # Quotes remain valid for 1 hour

    @classmethod
    def group_items_by_vendor(cls, cart_items):
        """
        Groups CartItem objects by their vendor (ProviderProfile) so items
        from the same seller share a single pickup & package calculation.
        """
        groups = defaultdict(list)
        for item in cart_items:
            provider_id = item.product.provider_id if item.product else 0
            groups[provider_id].append(item)

        shipment_groups = []
        for provider_id, items in groups.items():
            provider = items[0].product.provider if items[0].product else None
            origin_state = (provider.region if provider and provider.region else 'Rivers State')
            origin_address = (provider.store_address if provider and provider.store_address else 'Port Harcourt')

            total_weight = Decimal('0.00')
            has_heavy = False
            has_medium = False

            for c_item in items:
                prod = c_item.product
                unit_weight = getattr(prod, 'weight_kg', Decimal('1.00')) or Decimal('1.00')
                total_weight += (Decimal(str(unit_weight)) * c_item.quantity)

                s_class = getattr(prod, 'shipping_class', 'SMALL')
                if s_class == 'HEAVY':
                    has_heavy = True
                elif s_class == 'MEDIUM':
                    has_medium = True

            dominant_class = 'HEAVY' if has_heavy else ('MEDIUM' if has_medium else 'SMALL')

            shipment_groups.append({
                'provider_id': provider_id,
                'provider_name': provider.business_name if provider else 'AllThings Warehouse',
                'origin_state': origin_state,
                'origin_city': origin_address[:50],
                'total_weight_kg': float(total_weight),
                'shipping_class': dominant_class,
                'item_count': sum(i.quantity for i in items),
                'items': [i.product.name for i in items if i.product],
            })
        return shipment_groups

    @classmethod
    def _calculate_group_fee(cls, courier_code, route_type, shipping_class, total_weight_kg):
        """
        Calculates the shipping fee for a single vendor shipment group
        based on courier tier, route distance, package class, and weight.
        """
        weight = max(1.0, float(total_weight_kg))
        extra_kg = max(0.0, weight - 3.0)

        # Class multipliers
        class_surcharge = {
            'SMALL': 0,
            'MEDIUM': 1200,
            'HEAVY': 3500,
        }.get(shipping_class, 0)

        if courier_code == 'EXPRESS_DISPATCH':
            # Same-day Local Bike/Van Dispatch (Available for Intra-City & Intra-State only)
            if route_type not in ['INTRA_CITY', 'INTRA_STATE']:
                return None
            base = 1800 if route_type == 'INTRA_CITY' else 2500
            per_kg = 250
            fee = base + class_surcharge + (extra_kg * per_kg)
            eta = 'Same Day (2–5 Hours)' if route_type == 'INTRA_CITY' else 'Same / Next Day (4–12 Hours)'
            return {'fee': round(fee, -2), 'eta': eta}

        elif courier_code == 'GIGL':
            # GIG Logistics (Nationwide Doorstep Delivery)
            base_map = {
                'INTRA_CITY': 2500,
                'INTRA_STATE': 3200,
                'REGIONAL': 4800,
                'INTER_STATE': 6500,
            }
            per_kg_map = {
                'INTRA_CITY': 300,
                'INTRA_STATE': 350,
                'REGIONAL': 550,
                'INTER_STATE': 800,
            }
            eta_map = {
                'INTRA_CITY': '1–2 Working Days',
                'INTRA_STATE': '1–2 Working Days',
                'REGIONAL': '2–3 Working Days',
                'INTER_STATE': '3–5 Working Days',
            }
            fee = base_map[route_type] + class_surcharge + (extra_kg * per_kg_map[route_type])
            return {'fee': round(fee, -2), 'eta': eta_map[route_type]}

        elif courier_code == 'WAYBILL_CARGO':
            # Eco Waybill / Heavy Haulage Partner (Best price for bulky & multi-item orders)
            base_map = {
                'INTRA_CITY': 1500,
                'INTRA_STATE': 2000,
                'REGIONAL': 3500,
                'INTER_STATE': 4800,
            }
            per_kg_map = {
                'INTRA_CITY': 180,
                'INTRA_STATE': 220,
                'REGIONAL': 350,
                'INTER_STATE': 500,
            }
            eta_map = {
                'INTRA_CITY': '1–2 Working Days',
                'INTRA_STATE': '2–3 Working Days',
                'REGIONAL': '3–4 Working Days',
                'INTER_STATE': '4–6 Working Days',
            }
            fee = base_map[route_type] + (class_surcharge * 0.75) + (extra_kg * per_kg_map[route_type])
            return {'fee': round(fee, -2), 'eta': eta_map[route_type]}

        return None

    @classmethod
    def get_quotes_for_checkout(cls, cart_items, dest_state, dest_city=''):
        """
        Evaluates all supported couriers across every vendor shipment group in the cart.
        Returns normalized quote options with cryptographically signed tokens.
        """
        shipment_groups = cls.group_items_by_vendor(cart_items)
        if not shipment_groups:
            return {'quotes': [], 'shipment_groups': []}

        couriers = [
            {
                'code': 'EXPRESS_DISPATCH',
                'name': 'AllThings Express Dispatch',
                'description': 'Direct rider/van dispatch for local orders',
                'icon': 'fa-motorcycle',
            },
            {
                'code': 'GIGL',
                'name': 'GIG Logistics (Doorstep)',
                'description': 'Tracked doorstep courier with full insurance',
                'icon': 'fa-truck-fast',
            },
            {
                'code': 'WAYBILL_CARGO',
                'name': 'Eco Waybill & Heavy Cargo',
                'description': 'Cost-effective delivery for standard & bulky hardware',
                'icon': 'fa-boxes-stacked',
            },
        ]

        available_quotes = []

        for courier in couriers:
            total_fee = Decimal('0.00')
            courier_available_for_all_legs = True
            etas = []
            leg_breakdown = []

            for group in shipment_groups:
                route_type = classify_route(
                    group['origin_state'],
                    group['origin_city'],
                    dest_state,
                    dest_city
                )
                result = cls._calculate_group_fee(
                    courier['code'],
                    route_type,
                    group['shipping_class'],
                    group['total_weight_kg']
                )
                if result is None:
                    courier_available_for_all_legs = False
                    break

                leg_fee = Decimal(str(result['fee']))
                total_fee += leg_fee
                etas.append(result['eta'])
                leg_breakdown.append({
                    'provider_id': group['provider_id'],
                    'provider_name': group['provider_name'],
                    'fee': float(leg_fee),
                    'eta': result['eta'],
                })

            if courier_available_for_all_legs:
                # Sign the quote payload so the browser cannot tamper with the fee
                token_payload = {
                    'courier_code': courier['code'],
                    'courier_name': courier['name'],
                    'total_fee': str(total_fee),
                    'dest_state': normalize_location(dest_state),
                    'dest_city': normalize_location(dest_city),
                    'legs': leg_breakdown,
                }
                signed_token = signing.dumps(token_payload, salt=cls.SIGNING_SALT)

                available_quotes.append({
                    'courier_code': courier['code'],
                    'courier_name': courier['name'],
                    'description': courier['description'],
                    'icon': courier['icon'],
                    'amount': float(total_fee),
                    'estimated_delivery': etas[-1] if etas else '2–4 Working Days',
                    'legs': leg_breakdown,
                    'quote_token': signed_token,
                    'badge': '',
                })

        # Dynamically tag "Best Price" and "Fastest" based on actual returned quotes
        if available_quotes:
            cheapest = min(available_quotes, key=lambda q: q['amount'])
            cheapest['badge'] = 'Best Price'
            for q in available_quotes:
                if q['courier_code'] == 'EXPRESS_DISPATCH' and not q['badge']:
                    q['badge'] = 'Fastest'
                elif q['courier_code'] == 'GIGL' and not q['badge']:
                    q['badge'] = 'Recommended'

        return {
            'quotes': available_quotes,
            'shipment_groups': shipment_groups,
            'vendor_count': len(shipment_groups),
        }

    @classmethod
    def verify_quote_token(cls, token):
        """
        Verifies the cryptographic signature and age of a submitted shipping quote token.
        Returns the decoded dictionary or None if tampered/expired.
        """
        if not token:
            return None
        try:
            return signing.loads(
                token,
                salt=cls.SIGNING_SALT,
                max_age=cls.QUOTE_MAX_AGE_SECONDS
            )
        except signing.BadSignature:
            return None