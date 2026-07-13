"""
AI content moderation via GitHub Models API (OpenAI-compatible).
Falls back to keyword filter if API is unavailable.
"""
import aiohttp
import logging
import os

_AI_URL   = "https://models.inference.ai.azure.com/chat/completions"
_AI_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a strict content moderator for a Telegram advertising service in Russia. "
    "Determine whether the advertisement text contains ANY of the following FORBIDDEN content: "
    "1) Drugs, narcotics, psychoactive substances, drug shops, dark-market links, 'закладки' "
    "2) Online casino, gambling, slots, poker, roulette, sports betting, bookmakers "
    "Answer ONLY with one word: YES (contains forbidden content) or NO (clean). "
    "No explanations, no punctuation, just YES or NO."
)


async def ai_is_forbidden(text: str) -> bool | None:
    """
    Check if ad text is forbidden using GitHub Models GPT-4o-mini.
    Returns:
        True  — AI says forbidden
        False — AI says clean
        None  — API unavailable (caller should fall back to keyword check)
    """
    token = os.getenv("GH_AI_TOKEN") or os.getenv("GITHUB_TOKEN", "")
    if not token:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _AI_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": _AI_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user",   "content": f"Advertisement:\n{text[:1500]}"},
                    ],
                    "max_tokens":  5,
                    "temperature": 0.0,
                },
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                if resp.status == 200:
                    data   = await resp.json()
                    answer = data["choices"][0]["message"]["content"].strip().upper()
                    logging.info(f"[AI moderation] → {answer!r}")
                    return answer.startswith("YES")
                logging.warning(f"[AI moderation] HTTP {resp.status}")
    except Exception as exc:
        logging.warning(f"[AI moderation] unavailable: {exc}")

    return None   # signal: fall back to keyword filter
