import os
from dotenv import load_dotenv

load_dotenv()

# ─── Required ───────────────────────────────────────────
BOT_TOKEN:        str = os.getenv("BOT_TOKEN", "")
CRYPTO_PAY_TOKEN: str = os.getenv("CRYPTO_PAY_TOKEN", "")
ADMIN_ID:         int = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID:       int = int(os.getenv("CHANNEL_ID", "0"))

# ─── Optional ───────────────────────────────────────────
DEFAULT_PRICE:    float = float(os.getenv("DEFAULT_PRICE", "1.0"))

# ─── AI moderation (GitHub Models) ──────────────────────
# In GitHub Actions: automatically passed as GH_AI_TOKEN = secrets.GITHUB_TOKEN
# On VPS: set GH_AI_TOKEN to a GitHub PAT with models:read permission
GH_AI_TOKEN:      str = os.getenv("GH_AI_TOKEN", "")

# ─── Forbidden content patterns (keyword fallback) ──────
FORBIDDEN_WORDS = [
    "нарко", "наркот", "героин", "кокаин", "мефедрон",
    "амфетамин", "марихуан", "гашиш", "экстази", "спайс",
    "закладк", "шоп", "shop",
    "казино", "casino", "рулетк", "roulette",
    "ставк", "букмекер", "betting", "gambling",
    "слот", "slot", "покер", "poker"
]
