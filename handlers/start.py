import logging
import os
from aiogram import Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

# Cache for welcome photo file_id
WELCOME_PHOTO_CACHE: dict[str, str] = {}


# ── FSM States for chat-based registration ────────────────────────────────────
class RegForm(StatesGroup):
    name     = State()
    phone    = State()
    grade    = State()
    district = State()


def _build_start_keyboard():
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Ro'yxatdan o'tish",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Register via Chat",
                callback_data="start_registration",
            )
        ]])


async def cmd_start(message: types.Message) -> None:
    import os
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"

    state_store.set_state(user_id, state_store.STARTED)

    caption = (
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        "Rahimov School' xususiy maktabining foydali botiga xush kelibsiz 🎉\n\n"
        "Farzand tarbiyasiga doir foydali suhbat va darslarni ushbu botimizdan bepulga olasiz 🔥\n\n"
        "📝 Quyidagi tugma orqali ro'yxatdan o'tib, bepul darslarni tinglashingiz mumkin:"
    )

    from config import BASE_DIR
    from aiogram.types import InputFile

    cover_path = os.path.join(BASE_DIR, "static", "cover.png")
    sent_msg = None

    # Try Cache first
    cached_id = WELCOME_PHOTO_CACHE.get(cover_path)
    if cached_id:
        try:
            sent_msg = await message.answer_photo(
                photo=cached_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=_build_start_keyboard(),
            )
        except Exception:
            WELCOME_PHOTO_CACHE.pop(cover_path, None)

    if not sent_msg and os.path.exists(cover_path) and os.path.isfile(cover_path):
        try:
            sent_msg = await message.answer_photo(
                photo=InputFile(cover_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=_build_start_keyboard(),
            )
            if sent_msg.photo:
                WELCOME_PHOTO_CACHE[cover_path] = sent_msg.photo[-1].file_id
        except Exception as e:
            logger.error("❌ Failed to send welcome photo: %s", e)

    if not sent_msg:
        sent_msg = await message.answer(
            text=caption,
            parse_mode="HTML",
            reply_markup=_build_start_keyboard(),
        )

    # Store the message ID for later deletion after registration
    state_store.set_metadata(user_id, "reg_message_id", sent_msg.message_id)


# ── Chat-based registration flow ─────────────────────────────────────────────
async def cb_start_registration(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await RegForm.name.set()
    await callback.message.answer("✍️ To'liq ismingizni kiriting:", parse_mode="Markdown")


async def reg_get_name(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["name"] = message.text.strip()
    await RegForm.phone.set()
    await message.answer("📞 Telefon raqamingizni kiriting (masalan: +998901234567):", parse_mode="Markdown")


async def reg_get_phone(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["phone"] = message.text.strip()
    await RegForm.grade.set()
    await message.answer("🎓 Qaysi sinfda o'qiysiz? (masalan: 9, 10, 11):", parse_mode="Markdown")


async def reg_get_grade(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["grade"] = message.text.strip()
    await RegForm.district.set()
    await message.answer("📍 Qaysi tumandan ekansiz?", parse_mode="Markdown")


async def reg_get_district(message: types.Message, state: FSMContext) -> None:
    from services import sheets
    from handlers.webapp import _build_video_menu, _video_list_text

    async with state.proxy() as data:
        data["district"] = message.text.strip()
        reg_data = dict(data)

    user_id = message.from_user.id
    sheets.append_row({
        "name":        reg_data.get("name", ""),
        "phone":       reg_data.get("phone", ""),
        "grade":       reg_data.get("grade", ""),
        "district":    reg_data.get("district", ""),
        "source":      "Chat Registration",
        "telegram_id": user_id,
    })

    state_store.set_state(user_id, state_store.REGISTERED)
    await state.finish()

    await message.answer(
        text=(
            
            "🎧 Qaysi darsni tinglamoqchisiz?\n\n"
            f"{_video_list_text()}"
        ),
        reply_markup=_build_video_menu(),
    )
    
    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    reg_msg_id = state_store.get_metadata(user_id, "reg_message_id")
    if reg_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, reg_msg_id)
        except Exception:
            pass


def register_start_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_start, commands=["start"])

    if not WEBAPP_URL:
        dp.register_callback_query_handler(cb_start_registration, text="start_registration", state="*")
        dp.register_message_handler(reg_get_name,     state=RegForm.name)
        dp.register_message_handler(reg_get_phone,    state=RegForm.phone)
        dp.register_message_handler(reg_get_grade,    state=RegForm.grade)
        dp.register_message_handler(reg_get_district, state=RegForm.district)
