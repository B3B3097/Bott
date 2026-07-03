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
API_TOKEN = os.getenv("BOT_TOKEN", "7901691237:AAHJ6Rd88xBzGyesie7nIHDhKx8atZXegYg")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "599688:AAb9bDTJlBQdiJ2Cg6Qfu2wKbv2H0bOVSlT")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6315110467"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002246305003"))
DB_PATH = "bot_database.db"

# ==========================================
# 🚫 СУПЕР-РАСШИРЕННЫЙ ФИЛЬТР СЛОВ
# ==========================================
FORBIDDEN_KEYWORDS = [
    # Наркотики (сленг, химические названия, производные)
    "нарко", "соли", "меф", "шишки", "фен", "амф", "гашиш", "бошки", "план", "ск", "кристаллы",
    "трава", "кокаин", "героин", "мдма", "экстази", "гидра", "hydra", "mega", "darknet", "даркнет",
    "нарк", "narko", "shop", "шоп", "курьер", "клад", "закладка", "graffiti", "тесла", "tesla",
    "марихуана", "каннабис", "конопля", "гаш", "пластик", "скорость", "speed", "мет", "лсд", "lsd",
    "грибы", "психоделик", "химка", "спайс", "spice", "микс", "реагент", "порох", "белый", "круглые",
    # Казино и азартные игры (бренды, термины)
    "казино", "casino", "вулкан", "vulkan", "слоты", "slots", "рулетка", "ставка", "bet", "1xbet",
    "winline", "фонбет", "букмекер", "бк", "покер", "poker", "азарт", "джекпот", "jackpot",
    "melbet", "mostbet", "parimatch", "pin-up", "vavada", "вавада", "джойказино", "joycasino",
    "игровые автоматы", "крутить", "занос", "профит", "схемы", "взлом", "заработок", "инвестиции",
    "трейдинг", "сигналы", "binance", "крипта", "биткоин", "ethereum", "p2p", "арбитраж",
    # Обходные написания и символы
    "н.а.р.к.о", "к.а.з.и.н.о", "с.л.о.т.ы", "v.u.l.k.a.n", "n_a_r_k_o", "c_a_s_i_n_o",
    "н_а_р_к_о", "к_а_з_и_н_о", "k.a.z.i.n.o", "s.l.o.t.s", "н4рко", "к4зино", "сл0ты"
]

def check_content(text: str) -> bool:
    if not text: return True
    # Приводим к нижнему регистру и удаляем все не буквы/цифры для поиска скрытых слов
    text_lower = text.lower()
    clean_text = re.sub(r'[^а-яa-z0-9]', '', text_lower)
    
    # Замена похожих символов (leetspeak)
    leetspeak = {'0': 'о', '1': 'и', '3': 'е', '4': 'а', '5': 'с', '7': 'т', '8': 'в'}
    for k, v in leetspeak.items():
        clean_text = clean_text.replace(k, v)

    for word in FORBIDDEN_KEYWORDS:
        if word in text_lower or word in clean_text:
            logging.warning(f"Content blocked: found keyword '{word}'")
            return False
    return True

# ==========================================
# 💳 CRYPTO PAY API
# ==========================================
async def create_cryptobot_invoice(amount: float, asset: str = "USDT"):
    url = "https://pay.cryptobot.pay/api/createInvoice"
    params = {"asset": asset, "amount": str(amount), "description": "Рекламная ячейка / Донат"}
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            logging.error(f"Invoice error: {e}")
            return None

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
        except Exception as e:
            logging.error(f"Check payment error: {e}")
    return False

# ==========================================
# 🤖 ЛОГИКА БОТА
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return res[0] if res else default
    except: return default

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
    await message.answer(f"👋 Привет! Я бот для размещения рекламы.\n\n💰 Цена за 24 часа: {price} USDT\n📍 Всего доступно 2 ячейки.", reply_markup=kb)

# --- ДОНАТ ---
@dp.callback_query(F.data == "donate")
async def start_donate(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите сумму доната в ₽:")
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
            await message.answer(f"Счет на {amount_rub} ₽ создан. Оплатите в течение {timeout} мин. и нажмите кнопку проверки.", reply_markup=kb)
        else: await message.answer("❌ Ошибка при создании счета. Попробуйте позже.")
    except: await message.answer("Пожалуйста, введите корректное число.")

@dp.callback_query(F.data == "check_donate")
async def check_donate_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    invoice_id = data.get("invoice_id")
    if not invoice_id: return

    timeout_mins = int(get_setting('timeout', '2'))
    iterations = (timeout_mins * 60) // 5
    msg = await callback.message.answer(f"⏳ Проверяю оплату (ожидание до {timeout_mins} мин)...")
    
    for _ in range(iterations):
        if await check_cryptobot_payment(invoice_id):
            await msg.edit_text("✅ Спасибо за поддержку! Теперь вы можете отправить комментарий к донату:")
            await state.set_state(BotStates.waiting_for_donate_comment)
            return
        await asyncio.sleep(5)
    
    await msg.edit_text("❌ Оплата не обнаружена. Время ожидания истекло.")
    await state.clear()

@dp.message(BotStates.waiting_for_donate_comment)
async def process_donate_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_text = f"🧁 НОВЫЙ ДОНАТ: {data['amount']} ₽\n👤 От: @{message.from_user.username or message.from_user.id}\n💬 Комментарий: {message.text}"
    await bot.send_message(ADMIN_ID, admin_text)
    await message.answer("❤️ Спасибо! Ваш комментарий и донат получены.")
    await state.clear()

# --- РЕКЛАМА ---
@dp.callback_query(F.data == "status")
async def check_status(callback: types.CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    slots = conn.execute("SELECT id, is_free, expire_time FROM slots").fetchall()
    conn.close()
    text = "ℹ️ Статус рекламных ячеек:\n\n"
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
        await callback.answer("❌ Извините, все ячейки сейчас заняты!", show_alert=True)
        return
    await state.update_data(slot_id=free_slot[0])
    await callback.message.answer("Пришлите текст вашего рекламного объявления:")
    await state.set_state(BotStates.waiting_for_ad_text)

@dp.message(BotStates.waiting_for_ad_text)
async def process_ad_text(message: types.Message, state: FSMContext):
    if not check_content(message.text):
        await message.answer("❌ Ваше объявление содержит запрещенные темы (наркотики, казино и т.д.). Пожалуйста, измените текст.")
        return
    await state.update_data(ad_text=message.text, photos=[])
    await message.answer("Теперь пришлите фото (до 5 штук). Когда закончите, нажмите кнопку 'Готово'.", 
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
    await callback.message.answer("👀 Вот как будет выглядеть ваш пост:")
    try:
        if photos:
            if len(photos) == 1: await callback.message.answer_photo(photos[0], caption=text)
            else: await callback.message.answer_media_group([InputMediaPhoto(media=p, caption=text if i==0 else "") for i, p in enumerate(photos)])
        else: await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"Ошибка предпросмотра: {e}")

    price = float(get_setting('price', '1.0'))
    invoice = await create_cryptobot_invoice(price, "USDT")
    if invoice and invoice.get("ok"):
        await state.update_data(invoice_id=invoice['result']['invoice_id'])
        timeout = get_setting('timeout', '2')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить (CryptoBot)", url=invoice['result']['pay_url'])],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_ad_pay")]
        ])
        await callback.message.answer(f"💰 К оплате: {price} USDT\n⏳ Время на оплату: {timeout} мин.", reply_markup=kb)
    else: await callback.message.answer("❌ Ошибка при создании счета. Попробуйте позже.")

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
                await msg.edit_text("✅ Оплата подтверждена! Реклама опубликована в канале.")
                await state.clear(); return
            except Exception as e:
                await msg.edit_text(f"❌ Ошибка при публикации: {e}"); return
        await asyncio.sleep(5)
    await msg.edit_text("❌ Оплата не найдена. Время ожидания истекло."); await state.clear()

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
                    try: await bot.send_message(u[0], f"🔔 Внимание! Рекламная ячейка #{sid} освободилась. Успейте занять!")
                    except: pass
            conn.close()
        except Exception as e:
            logging.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)

# --- АДМИН ---
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    price = get_setting('price', '1.0')
    timeout = get_setting('timeout', '2')
    await message.answer(f"👑 ПАНЕЛЬ АДМИНИСТРАТОРА\n\n💰 Текущая цена: {price} USDT\n⏳ Тайм-аут оплаты: {timeout} мин.\n\nКоманды:\n/setprice [число]\n/settimeout [число]")

@dp.message(Command("setprice"), F.from_user.id == ADMIN_ID)
async def set_price(message: types.Message):
    try:
        p = float(message.text.split()[1])
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='price'", (str(p),))
        conn.commit(); conn.close()
        await message.answer(f"✅ Новая цена установлена: {p} USDT")
    except: await message.answer("Ошибка. Используйте: /setprice 5.0")

@dp.message(Command("settimeout"), F.from_user.id == ADMIN_ID)
async def set_timeout(message: types.Message):
    try:
        t = int(message.text.split()[1])
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='timeout'", (str(t),))
        conn.commit(); conn.close()
        await message.answer(f"✅ Новый тайм-аут установлен: {t} мин.")
    except: await message.answer("Ошибка. Используйте: /settimeout 5")

async def main():
    init_db()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            logging.error(f"Bot crashed, restarting... Error: {e}")
            time.sleep(5)
