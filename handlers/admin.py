from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import database as db
from config import ADMIN_ID

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    price = await db.get_price()
    await message.answer(
        f"👑 Панель администратора\n\n"
        f"Текущая цена за 24 часа: {price} USDT\n\n"
        f"Чтобы изменить цену, отправьте команду:\n"
        f"/setprice [новая_цена]"
    )

@router.message(Command("setprice"))
async def set_price(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /setprice [цена_в_USDT]")
        return
        
    try:
        new_price = float(args[1])
        if new_price <= 0:
            raise ValueError
            
        await db.set_price(new_price)
        await message.answer(f"✅ Цена успешно изменена на {new_price} USDT за 24 часа.")
    except ValueError:
        await message.answer("❌ Ошибка! Цена должна быть положительным числом.")
