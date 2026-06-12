import logging
import os
from aiogram import Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, InputMediaPhoto,
)
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

# Cache for welcome photo file_id
WELCOME_PHOTO_CACHE: dict[str, str] = {}


def _get_folder_image(folder_name: str) -> str:
    from config import BASE_DIR
    target_dir = os.path.join(BASE_DIR, "static", folder_name)
    if os.path.exists(target_dir) and os.path.isdir(target_dir):
        try:
            files = os.listdir(target_dir)
            images = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            if images:
                return os.path.join(target_dir, images[0])
        except Exception as e:
            logger.error("❌ Failed to read static/%s: %s", folder_name, e)
    return None


# ── FSM States for chat-based registration ────────────────────────────────────
class RegForm(StatesGroup):
    name     = State()
    phone    = State()
    grade    = State()
    district = State()


def _build_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🫖 Choy", callback_data="start_choy"),
            InlineKeyboardButton(text="☕️ Kofe", callback_data="start_kofe")
        ]
    ])


async def cb_start_buttons(callback: types.CallbackQuery) -> None:
    await callback.answer()
    
    from handlers.podcasts import _podcast_list_text, _podcast_list_keyboard
    from config import PODCASTS, BASE_DIR
    from aiogram.types import InputFile
    
    if not PODCASTS:
        await callback.message.answer("📹 Hozircha suhbatlar mavjud emas. Tez orada qo'shiladi!")
        return
        
    emoji_choice = "🫖 Choy" if callback.data == "start_choy" else "☕️ Kofe"
    text = (
        f"<b>{emoji_choice} o'rnida quyidagi qaysi darslardan qay birini tinglamoqchisiz?</b>\n\n"
        f"{_podcast_list_text()}"
    )
    
    # Select folder based on clicked button
    image_folder = "choy" if callback.data == "start_choy" else "kofe"
    photo_path = _get_folder_image(image_folder)
    if not photo_path:
        photo_path = _get_folder_image("start")
    if not photo_path:
        photo_path = os.path.join(BASE_DIR, "static", "cover.png")

    cache_key = None
    if os.path.exists(photo_path):
        try:
            cache_key = f"{photo_path}:{os.path.getmtime(photo_path)}"
        except Exception:
            cache_key = photo_path

    photo_input = None
    if cache_key:
        photo_input = WELCOME_PHOTO_CACHE.get(cache_key)

    if not photo_input and os.path.exists(photo_path):
        photo_input = InputFile(photo_path)

    try:
        if callback.message.photo:
            media = InputMediaPhoto(media=photo_input or photo_path, caption=text, parse_mode="HTML")
            sent_msg = await callback.message.edit_media(
                media=media,
                reply_markup=_podcast_list_keyboard()
            )
            if sent_msg and sent_msg.photo and cache_key and not WELCOME_PHOTO_CACHE.get(cache_key):
                WELCOME_PHOTO_CACHE[cache_key] = sent_msg.photo[-1].file_id
        else:
            if photo_path and os.path.exists(photo_path):
                await callback.message.answer_photo(
                    photo=photo_input or photo_path,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=_podcast_list_keyboard()
                )
                await callback.message.delete()
            else:
                await callback.message.edit_text(
                    text=text,
                    reply_markup=_podcast_list_keyboard(),
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Error editing welcome message: {e}")
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=_podcast_list_keyboard(),
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.answer(
                text=text,
                reply_markup=_podcast_list_keyboard(),
                parse_mode="HTML"
            )
        
    from handlers.webapp import _build_main_reply_keyboard
    await callback.message.answer(
        "Quyidagi menyu orqali darslar va boshqa bo'limlarni tanlashingiz mumkin:",
        reply_markup=_build_main_reply_keyboard()
    )


async def cmd_start(message: types.Message) -> None:
    import os
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"

    from config import ADMIN_IDS
    from handlers.webapp import _build_main_reply_keyboard

    from storage import settings_store
    settings = settings_store.get_settings()
    test_accounts = settings.get("test_accounts", [])
    is_test = user_id in test_accounts

    if is_test:
        state_store.delete_user(user_id)

    # Agar foydalanuvchi oldin ro'yxatdan o'tgan bo'lsa
    elif state_store.get_state(user_id) == state_store.REGISTERED or state_store.get_profile(user_id) is not None:
        await message.answer(
            f"👋 Assalomu alaykum, {first_name}!\n\n"
            "Asosiy menyuga xush kelibsiz. Quyidagi bo'limlardan birini tanlang:",
            reply_markup=_build_main_reply_keyboard()
        )
        return

    current_state = state_store.get_state(user_id)
    if current_state == state_store.PODCAST_SELECTED:
        await message.answer(
            f"👋 Assalomu alaykum, {first_name}!\n\n"
            "Suhbat va darslarni tanlash uchun quyidagi tugmalardan foydalaning:",
            reply_markup=_build_start_keyboard(),
        )
        return

    state_store.set_state(user_id, state_store.STARTED)

    caption = (
        "Assalomu alaykum, mehmon!\n\n"
        "Farzandingizni tarbiya qilishda yordamchi bo'ladigan botimizda sizni ko'rib turganimizdan xursandmiz 😊\n\n"
        "Odatda mehmonga choy yoki kofe taklif qilinadi ☕️\n\n"
        "Biz ham choy yoki kofe o'rnida farzandingizni tarbiya qilishda foyda beradigan bilimlar bermoqchimiz. Nima deysiz?\n\n"
        "Shunday qilib, qay birini tanlaysiz?"
    )

    from config import BASE_DIR
    from aiogram.types import InputFile

    cover_path = _get_folder_image("start")
    if not cover_path:
        cover_path = os.path.join(BASE_DIR, "static", "cover.png")

    sent_msg = None

    # Try Cache first using path and modification time
    cache_key = None
    if os.path.exists(cover_path):
        try:
            cache_key = f"{cover_path}:{os.path.getmtime(cover_path)}"
        except Exception:
            cache_key = cover_path

    if cache_key:
        cached_id = WELCOME_PHOTO_CACHE.get(cache_key)
        if cached_id:
            try:
                sent_msg = await message.answer_photo(
                    photo=cached_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=_build_start_keyboard(),
                )
            except Exception:
                WELCOME_PHOTO_CACHE.pop(cache_key, None)

    if not sent_msg and os.path.exists(cover_path) and os.path.isfile(cover_path):
        try:
            sent_msg = await message.answer_photo(
                photo=InputFile(cover_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=_build_start_keyboard(),
            )
            if sent_msg.photo and cache_key:
                WELCOME_PHOTO_CACHE[cache_key] = sent_msg.photo[-1].file_id
        except Exception as e:
            logger.error("❌ Failed to send welcome photo: %s", e)

    if not sent_msg:
        sent_msg = await message.answer(
            text=caption,
            parse_mode="HTML",
            reply_markup=_build_start_keyboard(),
        )

    # Store the message ID for later deletion if registration happens
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
    from handlers.webapp import _build_video_menu, _video_list_text, _build_main_reply_keyboard

    async with state.proxy() as data:
        data["district"] = message.text.strip()
        reg_data = dict(data)

    user_id = message.from_user.id

    from storage import settings_store
    settings = settings_store.get_settings()
    test_accounts = settings.get("test_accounts", [])
    is_test = user_id in test_accounts

    if not is_test:
        sheets.append_row({
            "name":        reg_data.get("name", ""),
            "phone":       reg_data.get("phone", ""),
            "grade":       reg_data.get("grade", ""),
            "district":    reg_data.get("district", ""),
            "source":      "Chat Registration",
            "telegram_id": user_id,
        })
        
    state_store.save_profile(
        user_id,
        name=reg_data.get("name", ""),
        phone=reg_data.get("phone", ""),
        grade=reg_data.get("grade", ""),
        district=reg_data.get("district", "")
    )

    state_store.set_state(user_id, state_store.REGISTERED)
    await state.finish()

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    reg_msg_id = state_store.get_metadata(user_id, "reg_message_id")
    if reg_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, reg_msg_id)
        except Exception:
            pass

    # Funnel: "Rahmat" + 10 sek + maktab savoli
    import asyncio
    from handlers.funnel import on_registered
    asyncio.create_task(on_registered(message.bot, user_id))


async def cmd_reset(message: types.Message) -> None:
    user_id = message.from_user.id
    state_store.delete_user(user_id)
    state_store.set_metadata(user_id, "funnel_state", None)
    state_store.set_metadata(user_id, "video_sent_ts", None)
    state_store.set_metadata(user_id, "snooze_ts", None)
    await message.answer("🔄 Barcha holatlaringiz o'chirildi va tozalandi!")
    await cmd_start(message)


def register_start_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_message_handler(cmd_reset, commands=["reset"])
    dp.register_callback_query_handler(cb_start_buttons, lambda c: c.data in ("start_choy", "start_kofe"), state="*")

    if not WEBAPP_URL:
        dp.register_callback_query_handler(cb_start_registration, text="start_registration", state="*")
        dp.register_message_handler(reg_get_name,     state=RegForm.name)
        dp.register_message_handler(reg_get_phone,    state=RegForm.phone)
        dp.register_message_handler(reg_get_grade,    state=RegForm.grade)
        dp.register_message_handler(reg_get_district, state=RegForm.district)
