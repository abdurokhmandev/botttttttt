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
        f"👋 Xush kelibsiz, {first_name}!\n\n"
        "Rahimov School ga xush kelibsiz.\n\n"
        "Bepul dars videolariga kirish uchun qisqacha ro'yxatdan o'ting. "
        "Bu atigi 30 soniya oladi! 🚀\n\n"
        "Pastdagi tugmani bosing 👇"
    )

    cover_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "cover.png")
    if os.path.exists(cover_path):
        with open(cover_path, "rb") as photo:
            await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=_build_start_keyboard(),
            )
    else:
        await message.answer(
            text=caption,
            parse_mode="Markdown",
            reply_markup=_build_start_keyboard(),
        )


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
            "Ro'yxatdan o'tdingiz! 🎉\n\n"
            "Quyidagi bepul darslardan birini tanlang:\n\n"
            f"{_video_list_text()}"
        ),
        reply_markup=_build_video_menu(),
    )


def register_start_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_start, commands=["start"])

    if not WEBAPP_URL:
        dp.register_callback_query_handler(cb_start_registration, text="start_registration", state="*")
        dp.register_message_handler(reg_get_name,     state=RegForm.name)
        dp.register_message_handler(reg_get_phone,    state=RegForm.phone)
        dp.register_message_handler(reg_get_grade,    state=RegForm.grade)
        dp.register_message_handler(reg_get_district, state=RegForm.district)
