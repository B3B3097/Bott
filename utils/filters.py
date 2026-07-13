import re
import asyncio
import logging

FORBIDDEN_PATTERNS = [
    r'нарко', r'наркот', r'героин', r'кокаин', r'мефедрон',
    r'амфетамин', r'марихуан', r'гашиш', r'экстази', r'спайс',
    r'соль\s*(для\s*ванн)?', r'закладк',
    r'купить\s*(наркот|траву|соль|мефедрон|кокаин)',
    r'шоп', r'shop', r'магазин\s*(наркот|закладок)',
    r'казино', r'casino', r'рулетк', r'roulette',
    r'ставк', r'букмекер', r'betting', r'gambling',
    r'слот', r'slot', r'покер', r'poker',
    r'игровые?\s*автомат', r'онлайн\s*игр',
]

def contains_forbidden_words(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    clean_text = re.sub(r'[\s\-_\.\*\|\/\\]', '', text_lower)
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text_lower):
            return True
        if re.search(pattern.replace(r'\s*', ''), clean_text):
            return True
    return False


async def is_forbidden(text: str) -> bool:
    """
    Two-layer check: AI first (GitHub Models), keyword fallback.
    Returns True if the text contains forbidden content.
    """
    try:
        from services.ai_moderation import ai_is_forbidden
        result = await ai_is_forbidden(text)
        if result is not None:
            return result
    except ImportError:
        pass
    except Exception as exc:
        logging.warning(f"[filters] AI check error: {exc}")

    return contains_forbidden_words(text)
