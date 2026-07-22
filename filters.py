import re
from config import CARD_BRANDS, COUNTRIES

# Common card number patterns
CARD_PATTERNS = [
    # Standard format: CC|Expiry|CVV
    r'(\d{13,19})\|(\d{2}/?\d{2,4})\|(\d{3,4})',
    # Format: CC:Expiry:CVV
    r'(\d{13,19}):(\d{2}/?\d{2,4}):(\d{3,4})',
    # Format: CC-Expiry-CVV
    r'(\d{13,19})-(\d{2}/?\d{2,4})-(\d{3,4})',
    # Format: CC Expiry CVV
    r'(\d{13,19})\s+(\d{2}/?\d{2,4})\s+(\d{3,4})',
    # Format: CC|Expiry|CVV|Extra
    r'(\d{13,19})\|(\d{2}/?\d{2,4})\|(\d{3,4})\|',
    # Just card number
    r'(\d{13,19})',
]

def luhn_check(card_number: str) -> bool:
    """Validate card number using Luhn algorithm"""
    try:
        digits = [int(d) for d in card_number]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        total = sum(odd_digits)
        for d in even_digits:
            total += sum(divmod(d * 2, 10))
        return total % 10 == 0
    except:
        return False

def luhn_check_fast(card_number: str) -> bool:
    """Fast Luhn check - inline for speed"""
    total = 0
    flip = False
    for c in reversed(card_number):
        d = ord(c) - 48
        if flip:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        flip = not flip
    return total % 10 == 0

def detect_card_brand(card_number: str) -> str:
    """Detect card brand from number"""
    for brand, prefixes in CARD_BRANDS.items():
        for prefix in prefixes:
            if card_number.startswith(prefix):
                return brand
    return "UNKNOWN"

def detect_country_from_bin(card_number: str) -> str:
    """Detect country from BIN (first 6 digits)"""
    if len(card_number) < 6:
        return "Unknown"
    
    bin_prefix = int(card_number[:6])
    
    # Simplified BIN to country mapping
    # In production, use a proper BIN database
    if 400000 <= bin_prefix <= 499999:
        return "US"  # Visa
    elif 510000 <= bin_prefix <= 559999:
        return "US"  # Mastercard
    elif 340000 <= bin_prefix <= 349999:
        return "US"  # Amex
    elif 370000 <= bin_prefix <= 379999:
        return "US"  # Amex
    elif 601100 <= bin_prefix <= 601199:
        return "US"  # Discover
    elif 350000 <= bin_prefix <= 359999:
        return "JP"  # JCB
    elif 620000 <= bin_prefix <= 629999:
        return "CN"  # UnionPay
    
    return "Unknown"

def parse_combo_line_fast(line: str) -> dict:
    """Parse combo line - INFINITY SPEED
    Supports formats:
    - cc|mm|yy|cvv
    - cc|yy|mm|cvv  
    - cc:mm:cvv
    - cc mm cvv
    """
    i = 0
    n = len(line)
    
    # Find first digit
    try:
        while not line[i].isdigit():
            i += 1
    except IndexError:
        return None
    
    # Get card number
    start = i
    try:
        while line[i].isdigit():
            i += 1
    except IndexError:
        pass
    
    card_len = i - start
    if card_len < 13 or card_len > 19:
        return None
    
    card_number = line[start:i]
    
    # Parse remaining parts: mm|yy|cvv or yy|mm|cvv
    parts = []
    while i < n and line[i] in '|:- \t':
        i += 1
    
    # Get all numeric parts
    while i < n:
        # Skip separators
        while i < n and line[i] in '|:- \t':
            i += 1
        if i >= n or not line[i].isdigit():
            break
        s = i
        while i < n and (line[i].isdigit() or line[i] == '/'):
            i += 1
        parts.append(line[s:i])
    
    # Determine expiry and cvv from parts
    expiry = ''
    cvv = ''
    
    if len(parts) >= 3:
        # Could be cc|mm|yy|cvv or cc|yy|mm|cvv
        p1, p2, p3 = parts[0], parts[1], parts[2]
        # If p1 looks like month (01-12) and p2 looks like year (20-99)
        if len(p1) == 2 and p1.isdigit() and 1 <= int(p1) <= 12 and len(p2) == 2:
            expiry = f"{p1}/{p2}"
            cvv = p3[:4]
        elif len(p2) == 2 and p2.isdigit() and 1 <= int(p2) <= 12 and len(p1) == 2:
            expiry = f"{p2}/{p1}"
            cvv = p3[:4]
        else:
            expiry = f"{p1}/{p2}"
            cvv = p3[:4]
    elif len(parts) == 2:
        # cc|mm|yy or cc|yy|cvv
        p1, p2 = parts[0], parts[1]
        if len(p1) == 2 and 1 <= int(p1) <= 12:
            expiry = p1
            cvv = p2[:4]
        else:
            expiry = p1
            cvv = p2[:4]
    elif len(parts) == 1:
        cvv = parts[0][:4]
    
    # Fast card type detection
    ct = 'UNKNOWN'
    c0 = card_number[0]
    if c0 == '4':
        ct = 'VISA'
    elif c0 == '5':
        ct = 'MASTERCARD'
    elif c0 == '3':
        if card_len > 1 and card_number[1] in '47':
            ct = 'AMEX'
        else:
            ct = 'JCB'
    elif c0 == '6':
        if card_number[:4] == '6011':
            ct = 'DISCOVER'
        elif card_number[:2] == '65':
            ct = 'DISCOVER'
        elif card_number[:2] == '62':
            ct = 'UNIONPAY'
    
    return (card_number, expiry, cvv, line, ct)

def filter_by_country(combo: dict, countries: list) -> bool:
    """Check if combo matches country filter"""
    if not countries:
        return True
    return combo.get('country', '').upper() in [c.upper() for c in countries]

def filter_by_card_type(combo: dict, card_types: list) -> bool:
    """Check if combo matches card type filter"""
    if not card_types:
        return True
    return combo.get('card_type', '').upper() in [ct.upper() for ct in card_types]

def filter_by_luhn(combo: dict) -> bool:
    """Check if combo passes Luhn validation"""
    return combo.get('is_valid_luhn', False)

def clean_combo_line(line: str) -> str:
    """Clean and normalize a combo line"""
    line = line.strip()
    # Remove extra whitespace
    line = re.sub(r'\s+', ' ', line)
    # Remove special characters except |:-
    line = re.sub(r'[^\w\s|:.\-/@]', '', line)
    return line

def split_combo_file(lines: list, max_lines: int = 100000) -> list:
    """Split combo file into chunks"""
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunks.append(lines[i:i + max_lines])
    return chunks

def get_combo_statistics(results: list) -> dict:
    """Calculate statistics from results"""
    stats = {
        'total': len(results),
        'valid_luhn': sum(1 for r in results if r.get('is_valid_luhn')),
        'by_type': {},
        'by_country': {},
    }
    
    for result in results:
        card_type = result.get('card_type', 'Unknown')
        country = result.get('country', 'Unknown')
        
        stats['by_type'][card_type] = stats['by_type'].get(card_type, 0) + 1
        stats['by_country'][country] = stats['by_country'].get(country, 0) + 1
    
    return stats
