import json
import logging

from aiogram import Dispatcher, types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

from config import VIDEOS
from services import sheets
from storage import state_store

logger = logging.getLogger(__name__)


def _build_video_menu() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=str(i), callback_data=f"video_{i}")
        for i in sorted(VIDEOS.keys())
    ]
    # Group buttons into rows of 5
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📹 Rahimov Suhbatlari"), KeyboardButton(text="Maktab haqida 🏫")],
            [KeyboardButton(text="🔗 Ijtimoiy tarmoqlarimiz"), KeyboardButton(text="📞 Telefon raqam")],
            [KeyboardButton(text="💬 Fikr va mulohazalar")],
        ],
        resize_keyboard=True
    )


def _video_list_text() -> str:
    lines = []
    for i in sorted(VIDEOS.keys()):
        title = VIDEOS.get(i, {}).get("title", f"Video {i}")
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


async def handle_web_app_data(message: types.Message) -> None:
    user_id = message.from_user.id
    if state_store.get_state(user_id) == state_store.REGISTERED:
        logger.info("⚠️ User %s already registered. Ignoring duplicate webapp message.", user_id)
        return
    raw = message.web_app_data.data

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON from WebApp for user %s: %s", user_id, raw)
        data = {}

    from storage import settings_store
    settings = settings_store.get_settings()
    test_accounts = settings.get("test_accounts", [])
    is_test = user_id in test_accounts

    if not is_test:
        sheets.append_row({
            "name":        data.get("name", ""),
            "phone":       data.get("phone", ""),
            "grade":       data.get("grade", ""),
            "district":    data.get("district", ""),
            "source":      data.get("source", "WebApp"),
            "telegram_id": user_id,
        })
        
    state_store.save_profile(
        user_id,
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        grade=data.get("grade", ""),
        district=data.get("district", ""),
    )

    state_store.set_state(user_id, state_store.REGISTERED)

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    try:
        await message.delete()
        reg_msg_id = state_store.get_metadata(user_id, "reg_message_id")
        if reg_msg_id:
            await message.bot.delete_message(message.chat.id, reg_msg_id)
    except Exception:
        pass

    # Funnel: "Rahmat" + 10 sek + maktab savoli
    import asyncio
    from handlers.funnel import on_registered
    asyncio.create_task(on_registered(message.bot, user_id))


async def webapp_api_handler(request: web.Request, bot: Bot) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    user_id = data.get("user_id")
    if not user_id:
        return web.json_response({"ok": False, "error": "Missing user_id"}, status=400)

    try:
        user_id_int = int(user_id)
    except ValueError:
        user_id_int = user_id

    if state_store.get_state(user_id_int) == state_store.REGISTERED:
        logger.info("⚠️ User %s already registered. Ignoring duplicate API call.", user_id_int)
        return web.json_response({"ok": True})

    from storage import settings_store
    settings = settings_store.get_settings()
    test_accounts = settings.get("test_accounts", [])
    is_test = user_id_int in test_accounts

    if not is_test:
        sheets.append_row({
            "name":        data.get("name", ""),
            "phone":       data.get("phone", ""),
            "grade":       data.get("grade", ""),
            "district":    data.get("district", ""),
            "source":      data.get("source", "WebApp"),
            "telegram_id": user_id_int,
        })
        
    state_store.save_profile(
        user_id_int,
        name=data.get("name", ""),
        phone=data.get("phone", ""),
        grade=data.get("grade", ""),
        district=data.get("district", ""),
    )

    state_store.set_state(user_id_int, state_store.REGISTERED)

    # Funnel: "Rahmat" + 10 sek + maktab savoli
    import asyncio
    from handlers.funnel import on_registered
    asyncio.create_task(on_registered(bot, user_id_int))

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    reg_msg_id = data.get("message_id") or state_store.get_metadata(user_id, "reg_message_id")
    if reg_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=reg_msg_id)
        except Exception:
            pass

    return web.json_response({"ok": True})


async def school_status_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    status = "✅" if callback.data == "school_yes" else "❌"
    
    from storage import settings_store
    settings = settings_store.get_settings()
    test_accounts = settings.get("test_accounts", [])
    is_test = user_id in test_accounts

    if not is_test:
        # Update local profile
        profile = state_store.get_profile(user_id)
        if profile:
            state_store.save_profile(
                user_id,
                name=profile.get("name", ""),
                phone=profile.get("phone", ""),
                grade=profile.get("grade", ""),
                district=profile.get("district", ""),
                school=status
            )

        # Update Google Sheets
        sheets.update_school_status(user_id, status)
    
    # Delete the question message
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Send success and video list
    await callback.bot.send_message(
        chat_id=user_id,
        text=(
            "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
            "🎧 Qaysi darsni tinglamoqchisiz?\n\n"
            f"{_video_list_text()}"
        ),
        reply_markup=_build_main_reply_keyboard(),
    )
    await callback.bot.send_message(
        chat_id=user_id,
        text="Pastdagi menyu orqali darslarni tanlashingiz mumkin:",
        reply_markup=_build_video_menu(),
    )
    await callback.answer()

def register_webapp_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(
        handle_web_app_data,
        content_types=types.ContentType.WEB_APP_DATA,
    )
    dp.register_callback_query_handler(
        school_status_callback,
        lambda c: c.data in ("school_yes", "school_no")
    )

