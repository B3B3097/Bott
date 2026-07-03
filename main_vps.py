import asyncio
import logging
import sqlite3
import os
import re
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

# ==========================================
# ⚙️ КОНФИГУРАЦИЯ
# ==========================================
API_TOKEN = "7901691237:AAHJ6Rd88xBzGyesie7nIHDhKx8atZXegYg"
CRYPTO_PAY_TOKEN = "599688:AAb9bDTJlBQdiJ2Cg6Qfu2wKbv2H0bOVSlT"
ADMIN_ID = 6315110467
CHANNEL_ID = -1002246305003
DB_PATH = "bot_database.db"

# ==========================================
# 🚫 РАСШИРЕННЫЙ ФИЛЬТР
# ==========================================
FORBIDDEN_KEYWORDS = [
    "нарко", "соли", "меф", "шишки", "фен", "амф", "гашиш", "бошки", "план", "ск", "кристаллы",
    "трава", "кокаин", "героин", "мдма", "экстази", "гидра", "hydra", "mega", "darknet", "даркнет",
    "казино", "casino", "вулкан", "vulkan", "слоты", "slots", "рулетка", "ставка", "bet", "1xbet",
    "winline", "фонбет", "букмекер", "бк", "покер", "poker", "азарт", "джекпот", "jackpot"
]

def check_content(text: str) -> bool:
    if not text: return True
    text = text.lower()
    clean_text = re.sub(r'[^а-яa-z0-9]', '', text)
    for word in FORBIDDEN_KEYWORDS:
        if word in text or word in clean_text:
            return False
    return True

# ==========================================
# 💳 CRYPTO PAY API
# ==========================================
async def create_cryptobot_invoice(amount: float, asset: str = "USDT"):
    url = "https://pay.cryptobot.pay/api/createInvoice"
    params = {"asset": asset, "amount": str(amount), "description": "Платеж в боте"}
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except: return None

async def check_cryptobot_payment(invoice_id):
    url = "https://pay.cryptobot.pay/api/getInvoices"
    params = {"invoice_ids": str(invoice_id)}
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if data.get("ok"):
                    items = data["result"]["items"]
                    if items and items[0]["status"] == "paid":
                        return True
        except: pass
    return False

# ==========================================
# 🤖 ЛОГИКА БОТА
# ==========================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class BotStates(StatesGroup):
    waiting_for_ad_text = State()
    waiting_for_ad_photos = State()
    waiting_for_donate_amount = State()
    waiting_for_donate_comment = State()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS slots (id INTEGER PRIMARY KEY, message_id INTEGER, expire_time DATETIME, is_free BOOLEAN DEFAULT 1)")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR IGNORE INTO slots (id, is_free) VALUES (1, 1), (2, 1)")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '1.0'), ('timeout', '2')")
    conn.commit()
    conn.close()

def get_setting(key, default):
    conn = sqlite3.connect(DB_PATH)
    res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return res[0] if res else default

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    price = get_setting('price', '1.0')
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Купить рекламу", callback_data="buy_ad")],
        [InlineKeyboardButton(text="📊 Статус ячеек", callback_data="status")],
        [InlineKeyboardButton(text="🧁 Отправить донат", callback_data="donate")]
    ])
    await message.answer(f"Привет! Размести рекламу в канале за {price} USDT или поддержи проект донатом.", reply_markup=kb)

# --- ДОНАТ ---
@dp.callback_query(F.data == "donate")
async def start_donate(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите сумму доната в ₽ (будет сконвертировано в USDT):")
    await state.set_state(BotStates.waiting_for_donate_amount)

@dp.message(BotStates.waiting_for_donate_amount)
async def process_donate_amount(message: types.Message, state: FSMContext):
    try:
        amount_rub = float(message.text.replace("₽", "").strip())
        invoice = await create_cryptobot_invoice(amount_rub, "RUB")
        if invoice and invoice.get("ok"):
            await state.update_data(invoice_id=invoice['result']['invoice_id'], amount=amount_rub)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice['result']['pay_url'])],
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_donate")]
            ])
            timeout = get_setting('timeout', '2')
            await message.answer(f"Счет на {amount_rub} ₽ создан. Оплатите в течение {timeout} мин.", reply_markup=kb)
        else: await message.answer("❌ Ошибка создания счета.")
    except: await message.answer("Введите число!")

@dp.callback_query(F.data == "check_donate")
async def check_donate_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("invoice_id")
    if not invoice_id: return

    timeout_mins = int(get_setting('timeout', '2'))
    iterations = (timeout_mins * 60) // 5
    msg = await callback.message.answer("⏳ Проверяю оплату...")
    
    for _ in range(iterations):
        if await check_cryptobot_payment(invoice_id):
            await msg.edit_text("✅ Спасибо за поддержку! Напишите комментарий к донату:")
            await state.set_state(BotStates.waiting_for_donate_comment)
            return
        await asyncio.sleep(5)
    
    await msg.edit_text("❌ Оплата не найдена. Время вышло.")
    await state.clear()

@dp.message(BotStates.waiting_for_donate_comment)
async def process_donate_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await bot.send_message(ADMIN_ID, f"🧁 НОВЫЙ ДОНАТ: {data['amount']} ₽\nОт: @{message.from_user.username or message.from_user.id}\nКомментарий: {message.text}")
    await message.answer("❤️ Ваш комментарий отправлен админу. Спасибо!")
    await state.clear()

# --- РЕКЛАМА ---
@dp.callback_query(F.data == "status")
async def check_status(callback: types.CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    slots = conn.execute("SELECT id, is_free, expire_time FROM slots").fetchall()
    conn.close()
    text = "ℹ️ Статус ячеек:\n\n"
    for s in slots:
        status = "✅ Свободна" if s[1] else f"🚫 Занята до {s[2]}"
        text += f"Ячейка #{s[0]}: {status}\n"
    await callback.message.answer(text)

@dp.callback_query(F.data == "buy_ad")
async def start_buy(callback: types.CallbackQuery, state: FSMContext):
    conn = sqlite3.connect(DB_PATH)
    free_slot = conn.execute("SELECT id FROM slots WHERE is_free=1 LIMIT 1").fetchone()
    conn.close()
    if not free_slot:
        await callback.answer("❌ Свободных мест нет!", show_alert=True)
        return
    await state.update_data(slot_id=free_slot[0])
    await callback.message.answer("Пришлите текст рекламного объявления:")
    await state.set_state(BotStates.waiting_for_ad_text)

@dp.message(BotStates.waiting_for_ad_text)
async def process_ad_text(message: types.Message, state: FSMContext):
    if not check_content(message.text):
        await message.answer("❌ Текст содержит запрещенные слова!")
        return
    await state.update_data(ad_text=message.text, photos=[])
    await message.answer("Теперь пришлите фото (до 5) и нажмите 'Готово'", 
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="ad_photos_done")]]))
    await state.set_state(BotStates.waiting_for_ad_photos)

@dp.message(BotStates.waiting_for_ad_photos, F.photo)
async def process_ad_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) < 5:
        photos.append(message.photo[-1].file_id)
        await state.update_data(photos=photos)

@dp.callback_query(F.data == "ad_photos_done", BotStates.waiting_for_ad_photos)
async def preview_ad(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = f"{data['ad_text']}\n\n#РЕКЛАМА"
    photos = data.get("photos", [])
    await callback.message.answer("👀 Предпросмотр:")
    if photos:
        if len(photos) == 1: await callback.message.answer_photo(photos[0], caption=text)
        else: await callback.message.answer_media_group([InputMediaPhoto(media=p, caption=text if i==0 else "") for i, p in enumerate(photos)])
    else: await callback.message.answer(text)
    
    price = float(get_setting('price', '1.0'))
    invoice = await create_cryptobot_invoice(price, "USDT")
    if invoice and invoice.get("ok"):
        await state.update_data(invoice_id=invoice['result']['invoice_id'])
        timeout = get_setting('timeout', '2')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice['result']['pay_url'])],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_ad_pay")]
        ])
        await callback.message.answer(f"💰 К оплате: {price} USDT\n⏳ У вас {timeout} мин.", reply_markup=kb)
    else: await callback.message.answer("❌ Ошибка счета.")

@dp.callback_query(F.data == "check_ad_pay")
async def check_ad_pay_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("invoice_id")
    if not invoice_id: return

    timeout_mins = int(get_setting('timeout', '2'))
    iterations = (timeout_mins * 60) // 5
    msg = await callback.message.answer("⏳ Проверяю оплату...")
    
    for _ in range(iterations):
        if await check_cryptobot_payment(invoice_id):
            slot_id = data['slot_id']
            text = f"{data['ad_text']}\n\n#РЕКЛАМА"
            photos = data.get("photos", [])
            try:
                if photos:
                    if len(photos) == 1: p_msg = await bot.send_photo(CHANNEL_ID, photos[0], caption=text)
                    else: 
                        p_msgs = await bot.send_media_group(CHANNEL_ID, [InputMediaPhoto(media=p, caption=text if i==0 else "") for i, p in enumerate(photos)])
                        p_msg = p_msgs[0]
                else: p_msg = await bot.send_message(CHANNEL_ID, text)
                
                expire = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect(DB_PATH)
                conn.execute("UPDATE slots SET message_id=?, expire_time=?, is_free=0 WHERE id=?", (p_msg.message_id, expire, slot_id))
                conn.commit(); conn.close()
                await msg.edit_text("✅ Опубликовано!")
                await state.clear(); return
            except Exception as e:
                await msg.edit_text(f"❌ Ошибка: {e}"); return
        await asyncio.sleep(5)
    await msg.edit_text("❌ Время вышло."); await state.clear()

# --- ПЛАНИРОВЩИК ---
async def scheduler():
    while True:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(DB_PATH)
            expired = conn.execute("SELECT id, message_id FROM slots WHERE is_free=0 AND expire_time <= ?", (now,)).fetchall()
            for sid, mid in expired:
                try: await bot.delete_message(CHANNEL_ID, mid)
                except: pass
                conn.execute("UPDATE slots SET is_free=1, message_id=NULL, expire_time=NULL WHERE id=?", (sid,))
                conn.commit()
                users = conn.execute("SELECT user_id FROM users").fetchall()
                for u in users:
                    try: await bot.send_message(u[0], f"🔔 Ячейка #{sid} свободна!")
                    except: pass
            conn.close()
        except: pass
        await asyncio.sleep(60)

# --- АДМИН ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    price = get_setting('price', '1.0')
    timeout = get_setting('timeout', '2')
    await message.answer(f"👑 Админ\nЦена: {price} USDT\nТайм-аут: {timeout} мин.\n/setprice [число]\n/settimeout [число]")

@dp.message(Command("setprice"), F.from_user.id == ADMIN_ID)
async def set_price(message: types.Message):
    try:
        p = float(message.text.split()[1]); conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='price'", (str(p),)); conn.commit(); conn.close()
        await message.answer(f"✅ Цена: {p} USDT")
    except: pass

@dp.message(Command("settimeout"), F.from_user.id == ADMIN_ID)
async def set_timeout(message: types.Message):
    try:
        t = int(message.text.split()[1]); conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='timeout'", (str(t),)); conn.commit(); conn.close()
        await message.answer(f"✅ Тайм-аут: {t} мин.")
    except: pass

async def main():
    init_db(); asyncio.create_task(scheduler()); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
