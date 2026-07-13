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
from config import CHANNEL_ID, ADMIN_ID
from utils.filters import is_forbidden
from services.crypto_pay import create_invoice, get_invoice
import json
from datetime import datetime, timedelta
import logging

router = Router()

# ═══════════════════════════ states ══════════════════════════════════════════

class AdState(StatesGroup):
    waiting_for_text   = State()
    waiting_for_photos = State()

class DonateState(StatesGroup):
    waiting_for_amount  = State()
    waiting_for_comment = State()

# ═══════════════════════════ /start ══════════════════════════════════════════

@router.message(Command("start"))
async def start_cmd(message: Message):
    await db.add_user(message.from_user.id)
    price = await db.get_price()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Купить рекламу",  callback_data="buy_ad")],
        [InlineKeyboardButton(text="🧁 Отправить донат", callback_data="donate")],
    ])
    await message.answer(
        f"👋 Привет! Я бот для размещения рекламы в канале.\n\n"
        f"У нас есть <b>2 рекламных места</b>. Каждое арендуется на <b>24 часа</b>.\n"
        f"Цена: <b>{price} USDT</b>. После срока пост удаляется автоматически.\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ═══════════════════════════ покупка рекламы ═════════════════════════════════

@router.callback_query(F.data == "buy_ad")
async def buy_ad_callback(callback: CallbackQuery, state: FSMContext):
    free_slots = await db.get_free_slots()
    if not free_slots:
        await callback.answer(
            "😔 Все рекламные места заняты.\nМы уведомим вас, когда освободится место!",
            show_alert=True
        )
        return
    price = await db.get_price()
    await callback.message.answer(
        f"✅ Свободных мест: <b>{len(free_slots)} из 2</b>\n"
        f"💰 Цена за 24 ч: <b>{price} USDT</b>\n\n"
        f"Пожалуйста, отправьте <b>текст</b> вашего рекламного поста.",
        parse_mode="HTML"
    )
    await state.set_state(AdState.waiting_for_text)
    await callback.answer()

@router.message(AdState.waiting_for_text)
async def process_ad_text(message: Message, state: FSMContext):
    text = message.text or message.caption
    if not text:
        await message.answer("Пожалуйста, отправьте текст вашего поста."); return

    if await is_forbidden(text):
        await message.answer(
            "❌ <b>Ваш текст содержит запрещённый контент.</b>\n\n"
            "Мы не принимаем рекламу:\n"
            "• Наркотиков и наркотических магазинов\n"
            "• Казино и азартных игр\n"
            "• Ставок и букмекерских контор\n\n"
            "Пожалуйста, измените текст и попробуйте снова.",
            parse_mode="HTML"
        ); return

    await state.update_data(ad_text=text, photos=[])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить фото", callback_data="skip_photos")]
    ])
    await message.answer(
        "✅ Текст принят!\n\n"
        "Теперь вы можете отправить до <b>5 фотографий</b> по одной.\n"
        "Или нажмите «Пропустить», если фото не нужны.",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await state.set_state(AdState.waiting_for_photos)

@router.message(AdState.waiting_for_photos, F.photo)
async def process_ad_photos(message: Message, state: FSMContext):
    data   = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 5:
        await message.answer("Максимум 5 фотографий. Нажмите «Готово»."); return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="finish_photos")]
    ])
    await message.answer(f"📷 Фото добавлено ({len(photos)}/5). Отправьте ещё или нажмите «Готово».", reply_markup=keyboard)

@router.message(AdState.waiting_for_photos)
async def non_photo_in_photos_state(message: Message):
    await message.answer("Пожалуйста, отправьте фотографию или нажмите «Пропустить».")

@router.callback_query(F.data.in_(["skip_photos", "finish_photos"]))
async def preview_ad(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data       = await state.get_data()
    text       = data.get("ad_text", "")
    photos     = data.get("photos", [])
    final_text = text + "\n\n#РЕКЛАМА"
    await state.update_data(final_text=final_text)

    await callback.message.answer("👁 <b>Предпросмотр вашего поста:</b>", parse_mode="HTML")
    try:
        if not photos:
            await callback.message.answer(final_text)
        elif len(photos) == 1:
            await callback.message.answer_photo(photo=photos[0], caption=final_text)
        else:
            media = [InputMediaPhoto(media=photos[0], caption=final_text)]
            for p in photos[1:]: media.append(InputMediaPhoto(media=p))
            await bot.send_media_group(chat_id=callback.message.chat.id, media=media)
    except Exception as e:
        logging.error(f"Preview error: {e}")
        await callback.message.answer("Ошибка предпросмотра. Попробуйте снова."); return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить к оплате", callback_data="pay_ad")],
        [InlineKeyboardButton(text="❌ Отменить",             callback_data="cancel_ad")],
    ])
    await callback.message.answer("Если пост выглядит правильно — нажмите «Продолжить к оплате».", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "cancel_ad")
async def cancel_ad(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Создание рекламы отменено. Возвращайтесь, когда будете готовы!")
    await callback.answer()

@router.callback_query(F.data == "pay_ad")
async def pay_ad(callback: CallbackQuery, state: FSMContext):
    free_slots = await db.get_free_slots()
    if not free_slots:
        await callback.answer("Пока вы создавали пост, все места заняли. Попробуйте позже.", show_alert=True)
        await state.clear(); return

    price   = await db.get_price()
    timeout = await db.get_timeout()
    slot_id = free_slots[0]
    payload = json.dumps({"user_id": callback.from_user.id, "slot_id": slot_id})

    try:
        invoice = await create_invoice(
            amount=price,
            description=f"Реклама в канале на 24 ч (ячейка #{slot_id})",
            payload=payload,
        )
        await state.update_data(invoice_id=invoice["invoice_id"], reserved_slot=slot_id)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить",        url=invoice["bot_invoice_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment")],
        ])
        await callback.message.answer(
            f"💰 Счёт на <b>{price} USDT</b> создан.\n\n"
            f"1. Нажмите «Оплатить» и оплатите через CryptoBot\n"
            f"2. Вернитесь и нажмите «Проверить оплату»\n\n"
            f"⏳ Время ожидания: <b>{timeout} мин.</b>",
            reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Invoice creation error: {e}")
        await callback.message.answer("❌ Ошибка при создании счёта. Попробуйте позже.")
    await callback.answer()

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data       = await state.get_data()
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        await callback.answer("Счёт не найден. Начните заново.", show_alert=True)
        await state.clear(); return

    invoice = await get_invoice(invoice_id)
    if not invoice:
        await callback.answer("Ошибка проверки. Попробуйте позже.", show_alert=True); return

    if invoice["status"] != "paid":
        await callback.answer("⏳ Оплата ещё не поступила. Оплатите счёт и попробуйте снова.", show_alert=True); return

    payload    = json.loads(invoice.get("payload", "{}"))
    slot_id    = payload.get("slot_id", data.get("reserved_slot"))
    free_slots = await db.get_free_slots()
    if slot_id not in free_slots:
        if free_slots: slot_id = free_slots[0]
        else:
            await callback.message.answer("⚠️ Все места заняты. Обратитесь к администратору для возврата средств.")
            await state.clear(); return

    text   = data.get("final_text", "")
    photos = data.get("photos", [])
    try:
        if not photos:
            post_msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
        elif len(photos) == 1:
            post_msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photos[0], caption=text)
        else:
            media = [InputMediaPhoto(media=photos[0], caption=text)]
            for p in photos[1:]: media.append(InputMediaPhoto(media=p))
            msgs = await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
            post_msg = msgs[0]

        expires_at = datetime.now() + timedelta(hours=24)
        await db.occupy_slot(slot_id=slot_id, user_id=callback.from_user.id,
                             post_id=post_msg.message_id, expires_at=expires_at.isoformat())
        await callback.message.answer(
            f"✅ <b>Оплата получена! Пост опубликован.</b>\n\n"
            f"📌 Ячейка: #{slot_id}\n"
            f"⏰ Будет удалён: {expires_at.strftime('%d.%m.%Y в %H:%M')} UTC",
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logging.error(f"Publishing error: {e}")
        await callback.message.answer(f"❌ Ошибка публикации: {e}\nОбратитесь к администратору.")

# ═══════════════════════════ донаты ══════════════════════════════════════════

@router.callback_query(F.data == "donate")
async def donate_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🧁 <b>Донат администратору</b>\n\n"
        "Введите сумму в <b>USDT</b> (минимум 0.1):",
        parse_mode="HTML"
    )
    await state.set_state(DonateState.waiting_for_amount)
    await callback.answer()

@router.message(DonateState.waiting_for_amount)
async def donate_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount < 0.1: raise ValueError
    except ValueError:
        await message.answer("❌ Введите число ≥ 0.1 (например: 1.5)"); return

    timeout = await db.get_timeout()
    try:
        invoice = await create_invoice(
            amount=amount,
            description="Донат администратору",
            payload=json.dumps({"type": "donate", "user_id": message.from_user.id}),
        )
        await state.update_data(invoice_id=invoice["invoice_id"], amount=amount)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить",        url=invoice["bot_invoice_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_donate")],
        ])
        await message.answer(
            f"💰 Счёт на <b>{amount} USDT</b> создан.\n"
            f"Оплатите и нажмите «Проверить оплату».\n\n"
            f"⏳ Тайм-аут: {timeout} мин.",
            reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Donate invoice error: {e}")
        await message.answer("❌ Ошибка при создании счёта. Попробуйте позже.")

@router.callback_query(F.data == "check_donate")
async def check_donate(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data       = await state.get_data()
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        await callback.answer("Счёт не найден.", show_alert=True); return

    invoice = await get_invoice(invoice_id)
    if not invoice:
        await callback.answer("Ошибка проверки.", show_alert=True); return

    if invoice["status"] != "paid":
        await callback.answer("⏳ Оплата ещё не поступила.", show_alert=True); return

    amount = data.get("amount", "?")
    await callback.message.answer(
        "✅ <b>Спасибо за поддержку!</b>\n\nНапишите комментарий к донату (или отправьте «-» без комментария):",
        parse_mode="HTML"
    )
    await state.set_state(DonateState.waiting_for_comment)
    await callback.answer()

@router.message(DonateState.waiting_for_comment)
async def donate_comment(message: Message, state: FSMContext, bot: Bot):
    data       = await state.get_data()
    amount     = data.get("amount", "?")
    comment    = message.text if message.text != "-" else "(без комментария)"
    username   = f"@{message.from_user.username}" if message.from_user.username else f"id:{message.from_user.id}"

    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🧁 <b>НОВЫЙ ДОНАТ</b>\n\n"
                f"Сумма: <b>{amount} USDT</b>\n"
                f"От: {username}\n"
                f"Комментарий: {comment}"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Admin notify error: {e}")

    await message.answer("❤️ Ваш комментарий отправлен администратору. Спасибо за поддержку!")
    await state.clear()
