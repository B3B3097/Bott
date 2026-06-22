import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
import database as db
from handlers import user, admin
from utils.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

async def main():
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    await db.init_db()
    
    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Include routers (admin first to avoid conflicts)
    dp.include_router(admin.router)
    dp.include_router(user.router)
    
    # Setup scheduler for slot expiry checks
    setup_scheduler(bot)
    
    # Start polling
    logging.info("Bot is starting...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
