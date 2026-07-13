from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import database as db
from config import ADMIN_ID
from datetime import datetime

router = Router()

def _admin_only(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not _admin_only(message): return
    price   = await db.get_price()
    timeout = await db.get_timeout()
    slots   = await db.get_all_slots()
    free    = sum(1 for s in slots if not s[1])
    await message.answer(
        f"👑 <b>Панель администратора</b>\n\n"
        f"💰 Цена за 24 ч: <b>{price} USDT</b>\n"
        f"⏳ Тайм-аут оплаты: <b>{timeout} мин.</b>\n"
        f"📌 Свободных ячеек: <b>{free}/2</b>\n\n"
        f"Команды:\n"
        f"/setprice [число]   — изменить цену USDT\n"
        f"/settimeout [мин]   — тайм-аут ожидания оплаты\n"
        f"/status             — статус ячеек\n"
        f"/slots              — то же самое",
        parse_mode="HTML"
    )

@router.message(Command("setprice"))
async def set_price(message: Message):
    if not _admin_only(message): return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /setprice [цена_в_USDT]"); return
    try:
        new_price = float(args[1])
        if new_price <= 0: raise ValueError
        await db.set_price(new_price)
        await message.answer(f"✅ Цена изменена на <b>{new_price} USDT</b> за 24 ч.", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Цена должна быть положительным числом.")

@router.message(Command("settimeout"))
async def set_timeout(message: Message):
    if not _admin_only(message): return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /settimeout [минуты]"); return
    try:
        mins = int(args[1])
        if mins < 1: raise ValueError
        await db.set_timeout(mins)
        await message.answer(f"✅ Тайм-аут оплаты: <b>{mins} мин.</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Укажите целое число минут (≥ 1).")

@router.message(Command(commands=["status", "slots"]))
async def slot_status(message: Message):
    if not _admin_only(message): return
    slots = await db.get_all_slots()
    lines = [f"📌 <b>Статус рекламных ячеек:</b>\n"]
    now = datetime.now()
    for slot_id, is_occ, expires_at_str in slots:
        if not is_occ:
            lines.append(f"  Ячейка #{slot_id}: ✅ Свободна")
        else:
            if expires_at_str:
                try:
                    exp = datetime.fromisoformat(expires_at_str)
                    remaining = exp - now
                    h = int(remaining.total_seconds() // 3600)
                    m = int((remaining.total_seconds() % 3600) // 60)
                    lines.append(f"  Ячейка #{slot_id}: 🚫 Занята, осталось {h}ч {m}м")
                except Exception:
                    lines.append(f"  Ячейка #{slot_id}: 🚫 Занята")
            else:
                lines.append(f"  Ячейка #{slot_id}: 🚫 Занята")
    await message.answer("\n".join(lines), parse_mode="HTML")
