import re

# Forbidden categories: drugs, drug shops, casino/gambling
FORBIDDEN_PATTERNS = [
    # Drugs (Russian)
    r'нарко',
    r'наркот',
    r'героин',
    r'кокаин',
    r'мефедрон',
    r'амфетамин',
    r'марихуан',
    r'гашиш',
    r'экстази',
    r'спайс',
    r'соль\s*(для\s*ванн)?',
    r'закладк',
    r'купить\s*(наркот|траву|соль|мефедрон|кокаин)',
    # Drug shops (Russian)
    r'шоп',
    r'shop',
    r'магазин\s*(наркот|закладок)',
    # Casino/Gambling (Russian and English)
    r'казино',
    r'casino',
    r'рулетк',
    r'roulette',
    r'ставк',
    r'букмекер',
    r'betting',
    r'bet',
    r'gambling',
    r'слот',
    r'slot',
    r'покер',
    r'poker',
    r'игровые?\s*автомат',
    r'онлайн\s*игр',
    r'выигрыш\s*(в|на)\s*(казино|игр)',
]

def contains_forbidden_words(text: str) -> bool:
    if not text:
        return False
        
    text_lower = text.lower()
    
    # Remove common obfuscation characters
    clean_text = re.sub(r'[\s\-_\.\*\|\/\\]', '', text_lower)
    
    for pattern in FORBIDDEN_PATTERNS:
        # Check in original text
        if re.search(pattern, text_lower):
            return True
        # Check in cleaned text
        if re.search(pattern.replace(r'\s*', ''), clean_text):
            return True
            
    return False
