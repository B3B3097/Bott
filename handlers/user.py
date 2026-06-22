from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from config import CHANNEL_ID
from utils.filters import contains_forbidden_words
from services.crypto_pay import create_invoice, get_invoice
import json
from datetime import datetime, timedelta
import logging

router = Router()

class AdState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photos = State()

# ─────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────

@router.message(Command("start"))
async def start_cmd(message: Message):
    await db.add_user(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Купить рекламу", callback_data="buy_ad")]
    ])
    
    await message.answer(
        "👋 Привет! Я бот для размещения рекламы в канале.\n\n"
        "У нас есть <b>2 рекламных места</b>. Каждое арендуется на <b>24 часа</b>.\n"
        "После истечения срока пост автоматически удаляется.\n\n"
        "Нажмите кнопку ниже, чтобы начать.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────
# Купить рекламу
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy_ad")
async def buy_ad_callback(callback: CallbackQuery, state: FSMContext):
    free_slots = await db.get_free_slots()
    
    if not free_slots:
        await callback.answer(
            "😔 Сейчас все рекламные места заняты.\n"
            "Мы уведомим вас, когда освободится место!",
            show_alert=True
        )
        return
        
    price = await db.get_price()
    
    await callback.message.answer(
        f"✅ Свободных мест: <b>{len(free_slots)} из 2</b>\n"
        f"💰 Цена за 24 часа: <b>{price} USDT</b>\n\n"
        f"Пожалуйста, отправьте <b>текст</b> вашего рекламного поста.",
        parse_mode="HTML"
    )
    await state.set_state(AdState.waiting_for_text)
    await callback.answer()

# ─────────────────────────────────────────────────────────
# Шаг 1: Текст поста
# ─────────────────────────────────────────────────────────

@router.message(AdState.waiting_for_text)
async def process_ad_text(message: Message, state: FSMContext):
    text = message.text or message.caption
    
    if not text:
        await message.answer("Пожалуйста, отправьте текст вашего поста.")
        return
        
    if contains_forbidden_words(text):
        await message.answer(
            "❌ <b>Ваш текст содержит запрещённый контент.</b>\n\n"
            "Мы не принимаем рекламу:\n"
            "• Наркотиков и наркотических магазинов\n"
            "• Казино и азартных игр\n"
            "• Ставок и букмекерских контор\n\n"
            "Пожалуйста, измените текст и попробуйте снова.",
            parse_mode="HTML"
        )
        return
        
    await state.update_data(ad_text=text, photos=[])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить фото", callback_data="skip_photos")]
    ])
    
    await message.answer(
        "✅ Текст принят!\n\n"
        "Теперь вы можете отправить до <b>5 фотографий</b> по одной.\n"
        "Или нажмите «Пропустить», если фото не нужны.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(AdState.waiting_for_photos)

# ─────────────────────────────────────────────────────────
# Шаг 2: Фотографии
# ─────────────────────────────────────────────────────────

@router.message(AdState.waiting_for_photos, F.photo)
async def process_ad_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) >= 5:
        await message.answer(
            "Вы уже загрузили максимальное количество фотографий (5).\n"
            "Нажмите «Готово», чтобы продолжить."
        )
        return
        
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="finish_photos")]
    ])
    
    await message.answer(
        f"📷 Фото добавлено ({len(photos)}/5).\n"
        f"Отправьте ещё или нажмите «Готово».",
        reply_markup=keyboard
    )

@router.message(AdState.waiting_for_photos)
async def process_non_photo_in_photos_state(message: Message):
    await message.answer("Пожалуйста, отправьте фотографию или нажмите «Пропустить».")

# ─────────────────────────────────────────────────────────
# Предпросмотр поста
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data.in_(["skip_photos", "finish_photos"]))
async def preview_ad(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get("ad_text", "")
    photos = data.get("photos", [])
    
    # Add #РЕКЛАМА tag
    final_text = text + "\n\n#РЕКЛАМА"
    await state.update_data(final_text=final_text)
    
    await callback.message.answer("👁 <b>Предпросмотр вашего поста:</b>", parse_mode="HTML")
    
    try:
        if not photos:
            await callback.message.answer(final_text)
        elif len(photos) == 1:
            await callback.message.answer_photo(photo=photos[0], caption=final_text)
        else:
            media_group = [InputMediaPhoto(media=photos[0], caption=final_text)]
            for photo_id in photos[1:]:
                media_group.append(InputMediaPhoto(media=photo_id))
            await bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)
    except Exception as e:
        logging.error(f"Preview error: {e}")
        await callback.message.answer("Ошибка предпросмотра. Попробуйте снова.")
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить к оплате", callback_data="pay_ad")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_ad")]
    ])
    
    await callback.message.answer(
        "Если пост выглядит правильно — нажмите «Продолжить к оплате».",
        reply_markup=keyboard
    )
    await callback.answer()

# ─────────────────────────────────────────────────────────
# Отмена
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel_ad")
async def cancel_ad(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Создание рекламы отменено. Возвращайтесь, когда будете готовы!")
    await callback.answer()

# ─────────────────────────────────────────────────────────
# Оплата
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "pay_ad")
async def pay_ad(callback: CallbackQuery, state: FSMContext):
    free_slots = await db.get_free_slots()
    if not free_slots:
        await callback.answer(
            "Пока вы создавали пост, все места заняли. Попробуйте позже.",
            show_alert=True
        )
        await state.clear()
        return
        
    price = await db.get_price()
    slot_id = free_slots[0]
    
    payload = json.dumps({
        "user_id": callback.from_user.id,
        "slot_id": slot_id
    })
    
    try:
        invoice = await create_invoice(
            amount=price,
            description=f"Реклама в канале на 24 часа (ячейка #{slot_id})",
            payload=payload
        )
        
        await state.update_data(invoice_id=invoice["invoice_id"], reserved_slot=slot_id)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=invoice["bot_invoice_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment")]
        ])
        
        await callback.message.answer(
            f"💰 Счёт на <b>{price} USDT</b> создан.\n\n"
            f"1. Нажмите «Оплатить» и оплатите через CryptoBot\n"
            f"2. Вернитесь сюда и нажмите «Проверить оплату»",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Invoice creation error: {e}")
        await callback.message.answer(
            "❌ Ошибка при создании счёта. Попробуйте позже или обратитесь к администратору."
        )
        
    await callback.answer()

# ─────────────────────────────────────────────────────────
# Проверка оплаты и публикация
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    invoice_id = data.get("invoice_id")
    
    if not invoice_id:
        await callback.answer("Счёт не найден. Начните заново.", show_alert=True)
        await state.clear()
        return
        
    invoice = await get_invoice(invoice_id)
    
    if not invoice:
        await callback.answer("Ошибка при проверке оплаты. Попробуйте позже.", show_alert=True)
        return
        
    if invoice["status"] != "paid":
        await callback.answer(
            "⏳ Оплата ещё не поступила. Оплатите счёт и попробуйте снова.",
            show_alert=True
        )
        return
        
    # Payment confirmed
    payload = json.loads(invoice.get("payload", "{}"))
    slot_id = payload.get("slot_id", data.get("reserved_slot"))
    
    # Verify slot is still free
    free_slots = await db.get_free_slots()
    if slot_id not in free_slots:
        if free_slots:
            slot_id = free_slots[0]
        else:
            await callback.message.answer(
                "⚠️ Все рекламные места заняты. Обратитесь к администратору для возврата средств."
            )
            await state.clear()
            return
    
    text = data.get("final_text", "")
    photos = data.get("photos", [])
    
    try:
        post_msg = None
        
        if not photos:
            post_msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
        elif len(photos) == 1:
            post_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photos[0], caption=text)
        else:
            media_group = [InputMediaPhoto(media=photos[0], caption=text)]
            for photo_id in photos[1:]:
                media_group.append(InputMediaPhoto(media=photo_id))
            msgs = await bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
            post_msg = msgs[0]
            
        expires_at = datetime.now() + timedelta(hours=24)
        
        await db.occupy_slot(
            slot_id=slot_id,
            user_id=callback.from_user.id,
            post_id=post_msg.message_id,
            expires_at=expires_at.isoformat()
        )
        
        await callback.message.answer(
            f"✅ <b>Оплата получена! Пост опубликован.</b>\n\n"
            f"📌 Ячейка: #{slot_id}\n"
            f"⏰ Пост будет удалён: {expires_at.strftime('%d.%m.%Y в %H:%M')} UTC",
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        logging.error(f"Post publishing error: {e}")
        await callback.message.answer(
            f"❌ Ошибка при публикации поста: {e}\n"
            f"Обратитесь к администратору."
        )
