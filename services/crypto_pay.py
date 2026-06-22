import aiohttp
import logging
from config import CRYPTO_PAY_TOKEN

CRYPTO_API_URL = "https://pay.crypt.bot/api"

async def create_invoice(amount: float, description: str, payload: str) -> dict:
    """
    Create a payment invoice via CryptoPay API.
    Returns invoice dict with 'invoice_id' and 'bot_invoice_url'.
    """
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN
    }
    
    data = {
        "asset": "USDT",
        "amount": str(round(amount, 2)),
        "description": description,
        "payload": payload,
        "allow_comments": False,
        "allow_anonymous": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CRYPTO_API_URL}/createInvoice", headers=headers, json=data) as response:
            result = await response.json()
            if result.get("ok"):
                return result["result"]
            else:
                logging.error(f"CryptoPay createInvoice error: {result}")
                raise Exception(f"Failed to create invoice: {result.get('error', 'Unknown error')}")

async def get_invoice(invoice_id: int) -> dict | None:
    """
    Get invoice status by ID.
    Returns invoice dict or None if not found.
    """
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN
    }
    
    params = {
        "invoice_ids": str(invoice_id)
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRYPTO_API_URL}/getInvoices", headers=headers, params=params) as response:
            result = await response.json()
            if result.get("ok"):
                items = result["result"].get("items", [])
                return items[0] if items else None
            else:
                logging.error(f"CryptoPay getInvoices error: {result}")
                return None

async def get_invoices(invoice_ids: str) -> list:
    """
    Get multiple invoices by comma-separated IDs.
    """
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN
    }
    
    params = {
        "invoice_ids": invoice_ids
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CRYPTO_API_URL}/getInvoices", headers=headers, params=params) as response:
            result = await response.json()
            if result.get("ok"):
                return result["result"].get("items", [])
            else:
                logging.error(f"CryptoPay getInvoices error: {result}")
                return []
