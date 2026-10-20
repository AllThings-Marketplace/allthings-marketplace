import re
from decimal import Decimal

def parse_search_intent(query_string):
    """
    Translates raw user searches into structured database filters.
    """
    query = query_string.lower().strip()
    
    intent = {
        'clean_query': query,
        'max_price': None,
        'min_price': None,
        'is_service_request': False,
        'location': None
    }

    # 1. Max Budget Extraction (e.g., "under 50k", "below 100000", "max 20k")
    max_budget_pattern = r'\b(under|below|max|less than)\s*(\d+)(k)?\b'
    max_match = re.search(max_budget_pattern, query)
    if max_match:
        amount = int(max_match.group(2))
        if max_match.group(3) == 'k':
            amount *= 1000
        intent['max_price'] = Decimal(amount)
        query = re.sub(max_budget_pattern, '', query).strip()

    # 2. Min Budget Extraction (e.g., "above 50k", "over 100k", "min 20k")
    min_budget_pattern = r'\b(above|over|min|more than)\s*(\d+)(k)?\b'
    min_match = re.search(min_budget_pattern, query)
    if min_match:
        amount = int(min_match.group(2))
        if min_match.group(3) == 'k':
            amount *= 1000
        intent['min_price'] = Decimal(amount)
        query = re.sub(min_budget_pattern, '', query).strip()

    # 3. Location Extraction (e.g., "in Oyigbo", "around Port Harcourt")
    location_pattern = r'\b(in|around|near)\s+([a-z\s]+)$'
    location_match = re.search(location_pattern, query)
    if location_match:
        intent['location'] = location_match.group(2).strip()
        query = re.sub(location_pattern, '', query).strip()

    # 4. Service Intent Detection & Verb Cleaning
    # Action words that trigger service mode AND get stripped so the core noun (e.g., "AC", "generator") matches
    service_verbs = ['fix', 'repair', 'install', 'installation', 'maintenance', 'service']
    service_nouns = ['technician', 'plumber', 'electrician', 'mechanic', 'installer']
    
    if any(re.search(rf'\b{word}\b', query) for word in service_verbs + service_nouns):
        intent['is_service_request'] = True
        for verb in service_verbs:
            query = re.sub(rf'\b{verb}\b', '', query).strip()

    # 5. Strip Conversational Filler Words
    stop_words = ['i', 'need', 'want', 'looking', 'for', 'someone', 'to', 'my', 'a', 'an', 'the', 'cheap', 'best']
    for word in stop_words:
        query = re.sub(rf'\b{word}\b', '', query).strip()

    # Collapse any multiple spaces left behind
    intent['clean_query'] = re.sub(r'\s+', ' ', query).strip()

    return intent