import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import ADMIN_IDS
from storage import state_store

logger = logging.getLogger(__name__)

class BroadcastStates(StatesGroup):
    SELECT_AUDIENCE = State()
    GET_CONTENT = State()
    GET_BUTTON = State()
    CONFIRM = State()

def _admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📢 Xabar yuborish")],
            [KeyboardButton("📊 Statistika")]
        ],
        resize_keyboard=True
    )

def _audience_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Barchaga", callback_data="target_all")],
        [InlineKeyboardButton(text="❌ Ro'yxatdan o'tmaganlarga", callback_data="target_unregistered")],
        [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="cancel_broadcast")]
    ])

def _confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])

# ── Admin Main ───────────────────────────────────────────────────────────────

async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "👋 Admin panelga xush kelibsiz!",
        reply_markup=_admin_main_keyboard()
    )

async def show_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    all_users = state_store.get_all()
    total = len(all_users)
    registered = sum(1 for u in all_users.values() if u.get("state") == state_store.REGISTERED)
    
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: {total}\n"
        f"✅ Ro'yxatdan o'tganlar: {registered}\n"
        f"⏳ Ro'yxatdan o'tmaganlar: {total - registered}"
    )
    await message.answer(text, parse_mode="HTML")

# ── Broadcast Flow ────────────────────────────────────────────────────────────

async def start_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await BroadcastStates.SELECT_AUDIENCE.set()
    await message.answer(
        "🎯 Kimlarga xabar yubormoqchisiz?",
        reply_markup=_audience_keyboard()
    )

async def set_target(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_broadcast":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    target = "all" if callback.data == "target_all" else "unregistered"
    await state.update_data(target=target)
    
    await BroadcastStates.GET_CONTENT.set()
    await callback.message.edit_text(
        "📝 Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video va h.k.):"
    )

async def get_content(message: types.Message, state: FSMContext):
    # Store the entire message to copy it later
    await state.update_data(message_id=message.message_id, chat_id=message.chat.id)
    
    await BroadcastStates.GET_BUTTON.set()
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Tugmasiz yuborish", callback_data="skip_button")]
    ])
    await message.answer(
        "🔗 Tugma qo'shishni xohlaysizmi?\n\n"
        "Format: <code>Tugma matni | Link</code>\n"
        "Masalan: <code>Bizning kanal | https://t.me/...</code>",
        parse_mode="HTML",
        reply_markup=markup
    )

async def get_button(message: types.Message, state: FSMContext):
    if "|" not in message.text:
        await message.answer("❌ Noto'g'ri format. Qaytadan urinib ko'ring yoki pastdagi tugmani bosing.")
        return
    
    text, url = message.text.split("|", 1)
    await state.update_data(btn_text=text.strip(), btn_url=url.strip())
    
    await BroadcastStates.CONFIRM.set()
    await _show_preview(message, state)

async def skip_button(callback: types.CallbackQuery, state: FSMContext):
    await BroadcastStates.CONFIRM.set()
    await _show_preview(callback.message, state)

async def _show_preview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    await message.answer("👀 <b>Xabar ko'rinishi (Preview):</b>", parse_mode="HTML")
    
    # Send a copy of the message with the button
    markup = None
    if data.get("btn_text") and data.get("btn_url"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=data["btn_text"], url=data["btn_url"])]
        ])
    
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=data["chat_id"],
        message_id=data["message_id"],
        reply_markup=markup
    )
    
    target_text = "Barchaga" if data["target"] == "all" else "Ro'yxatdan o'tmaganlarga"
    await message.answer(
        f"⬆️ Xabar yuqoridagidek ko'rinadi.\n🎯 Maqsadli auditoriya: <b>{target_text}</b>\n\nTasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard()
    )

async def execute_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_broadcast":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    data = await state.get_data()
    await state.finish()
    
    await callback.message.edit_text("🚀 Yuborish boshlandi...")
    
    all_users = state_store.get_all()
    target = data["target"]
    
    # Prepare markup
    markup = None
    if data.get("btn_text") and data.get("btn_url"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=data["btn_text"], url=data["btn_url"])]
        ])

    count = 0
    failed = 0
    
    for user_id, info in all_users.items():
        # Filter logic
        if target == "unregistered" and info.get("state") == state_store.REGISTERED:
            continue
            
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=data["chat_id"],
                message_id=data["message_id"],
                reply_markup=markup
            )
            count += 1
            # Rate limiting (optional but safe)
            if count % 20 == 0:
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error("Failed to send broadcast to %s: %s", user_id, e)
            failed += 1

    await callback.message.answer(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"👤 Qabul qildi: {count}\n"
        f"❌ Xatolik: {failed}",
        parse_mode="HTML",
        reply_markup=_admin_main_keyboard()
    )

# ── Registration ──────────────────────────────────────────────────────────────

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_admin, commands=["admin"], state="*")
    dp.register_message_handler(show_stats, lambda m: m.text == "📊 Statistika", state="*")
    dp.register_message_handler(start_broadcast, lambda m: m.text == "📢 Xabar yuborish", state="*")
    
    dp.register_callback_query_handler(set_target, state=BroadcastStates.SELECT_AUDIENCE)
    dp.register_message_handler(get_content, content_types=types.ContentType.ANY, state=BroadcastStates.GET_CONTENT)
    dp.register_callback_query_handler(skip_button, lambda c: c.data == "skip_button", state=BroadcastStates.GET_BUTTON)
    dp.register_message_handler(get_button, state=BroadcastStates.GET_BUTTON)
    dp.register_callback_query_handler(execute_broadcast, state=BroadcastStates.CONFIRM)
