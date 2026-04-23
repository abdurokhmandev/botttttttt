from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import WEBAPP_URL
from storage import state_store


# ── FSM States for chat-based registration ────────────────────────────────────
class RegForm(StatesGroup):
    name     = State()
    phone    = State()
    grade    = State()
    district = State()


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

def _build_start_keyboard():
    if WEBAPP_URL:
        # Full Mini App button MUST be a ReplyKeyboardMarkup to support sendData
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton(
            text="📝 Register",
            web_app=WebAppInfo(url=WEBAPP_URL)
        ))
        return keyboard
    else:
        # Fallback: chat-based registration
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Register via Chat",
                callback_data="start_registration",
            )
        ]])


async def cmd_start(message: types.Message) -> None:
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"

    state_store.set_state(user_id, state_store.STARTED)

    await message.answer(
        text=(
            f"👋 Welcome, {first_name}!\n\n"
            "We're glad you found Rahimov School.\n\n"
            "To access your *free lesson videos*, please complete a quick registration form. "
            "It only takes 30 seconds! 🚀\n\n"
            "Tap the button below to get started 👇"
        ),
        parse_mode="Markdown",
        reply_markup=_build_start_keyboard(),
    )


# ── Chat-based registration flow ─────────────────────────────────────────────
async def cb_start_registration(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await RegForm.name.set()
    await callback.message.answer("✍️ Please enter your *full name*:", parse_mode="Markdown")


async def reg_get_name(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["name"] = message.text.strip()
    await RegForm.phone.set()
    await message.answer("📞 Enter your *phone number* (e.g. +998901234567):", parse_mode="Markdown")


async def reg_get_phone(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["phone"] = message.text.strip()
    await RegForm.grade.set()
    await message.answer("🎓 Which *grade* are you in? (e.g. 9, 10, 11):", parse_mode="Markdown")


async def reg_get_grade(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data["grade"] = message.text.strip()
    await RegForm.district.set()
    await message.answer("📍 Which *district* are you from?", parse_mode="Markdown")


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
            "Thank you for registering! 🎉\n\n"
            "Choose a free lesson below:\n\n"
            f"{_video_list_text()}"
        ),
        parse_mode="Markdown",
        reply_markup=_build_video_menu(),
    )


def register_start_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_start, commands=["start"])

    # Only register chat-registration handlers if no webapp URL
    if not WEBAPP_URL:
        dp.register_callback_query_handler(cb_start_registration, text="start_registration", state="*")
        dp.register_message_handler(reg_get_name,     state=RegForm.name)
        dp.register_message_handler(reg_get_phone,    state=RegForm.phone)
        dp.register_message_handler(reg_get_grade,    state=RegForm.grade)
        dp.register_message_handler(reg_get_district, state=RegForm.district)

