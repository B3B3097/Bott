import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# ─── Required ───────────────────────────────────────────
BOT_TOKEN:        str = os.getenv("BOT_TOKEN", "")
CRYPTO_PAY_TOKEN: str = os.getenv("CRYPTO_PAY_TOKEN", "")

# ─── Admin / Channel (can be set later via /setadmin) ───
def _parse_int(name: str, default: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning(f"[config] {name}={raw!r} is not a valid integer, using {default}")
        return default

ADMIN_ID:   int = _parse_int("ADMIN_ID",   0)
CHANNEL_ID: int = _parse_int("CHANNEL_ID", 0)

# ─── Optional ───────────────────────────────────────────
DEFAULT_PRICE: float = float(os.getenv("DEFAULT_PRICE", "1.0"))

# ─── AI moderation (GitHub Models) ──────────────────────
GH_AI_TOKEN: str = os.getenv("GH_AI_TOKEN", "")

# ─── Forbidden content patterns (keyword fallback) ──────
FORBIDDEN_WORDS = [
    "нарко", "наркот", "героин", "кокаин", "мефедрон",
    "амфетамин", "марихуан", "гашиш", "экстази", "спайс",
    "закладк", "шоп", "shop",
    "казино", "casino", "рулетк", "roulette",
    "ставк", "букмекер", "betting", "gambling",
    "слот", "slot", "покер", "poker"
]

# ─── Startup validation ─────────────────────────────────
def validate():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if not CRYPTO_PAY_TOKEN:
        errors.append("CRYPTO_PAY_TOKEN is not set")
    if ADMIN_ID == 0:
        logging.warning(
            "[config] ADMIN_ID is not set — admin commands will be disabled. "
            "Set ADMIN_ID secret in GitHub repo settings."
        )
    if CHANNEL_ID == 0:
        logging.warning(
            "[config] CHANNEL_ID is not set — posts cannot be published to channel. "
            "Set CHANNEL_ID secret in GitHub repo settings."
        )
    if errors:
        for e in errors:
            logging.critical(f"[config] MISSING: {e}")
        sys.exit(1)
