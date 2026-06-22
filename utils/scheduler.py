from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from config import CHANNEL_ID
from datetime import datetime
import logging

scheduler = AsyncIOScheduler(timezone="UTC")

async def check_expired_slots(bot: Bot):
    """
    Periodically checks if any ad slots have expired.
    If expired: deletes the post from channel, frees the slot,
    and notifies all users in the database.
    """
    try:
        occupied_slots = await db.get_occupied_slots()
        now = datetime.now()
        
        for slot_id, post_id, expires_at_str in occupied_slots:
            if not expires_at_str:
                continue
                
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
            except ValueError:
                logging.error(f"Invalid expires_at format for slot {slot_id}: {expires_at_str}")
                continue
            
            if now >= expires_at:
                logging.info(f"Slot #{slot_id} expired. Deleting post {post_id}...")
                
                # Try to delete post from channel
                if post_id:
                    try:
                        await bot.delete_message(chat_id=CHANNEL_ID, message_id=post_id)
                        logging.info(f"Post {post_id} deleted from channel.")
                    except Exception as e:
                        logging.error(f"Failed to delete post {post_id} from channel: {e}")
                        
                # Free the slot in database
                await db.free_slot(slot_id)
                logging.info(f"Slot #{slot_id} freed.")
                
                # Notify all users
                users = await db.get_all_users()
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Купить рекламу", callback_data="buy_ad")]
                ])
                
                for user_id in users:
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"🟢 Ячейка #{slot_id} для рекламы освободилась!\n\n"
                                f"Теперь вы можете разместить свою рекламу. "
                                f"Нажмите кнопку ниже, чтобы забронировать место."
                            ),
                            reply_markup=keyboard
                        )
                    except Exception as e:
                        logging.warning(f"Could not notify user {user_id}: {e}")
                        
    except Exception as e:
        logging.error(f"Error in check_expired_slots: {e}")

def setup_scheduler(bot: Bot):
    """Setup and start the APScheduler."""
    scheduler.add_job(
        check_expired_slots,
        trigger='interval',
        minutes=5,
        args=[bot],
        id='check_slots',
        replace_existing=True
    )
    scheduler.start()
    logging.info("Scheduler started. Checking slots every 5 minutes.")
