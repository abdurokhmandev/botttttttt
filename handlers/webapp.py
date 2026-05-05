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
        for i in range(1, 6)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _build_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏫 Rahimov School"), KeyboardButton(text="📹 Rahimov Suhbatlari")],
            [KeyboardButton(text="🔗 Ijtimoiy tarmoqlarimiz"), KeyboardButton(text="📞 Telefon raqam")]
        ],
        resize_keyboard=True
    )


def _video_list_text() -> str:
    lines = []
    for i in range(1, 6):
        title = VIDEOS.get(i, {}).get("title", f"Video {i}")
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


async def handle_web_app_data(message: types.Message) -> None:
    user_id = message.from_user.id
    raw = message.web_app_data.data

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON from WebApp for user %s: %s", user_id, raw)
        data = {}

    sheets.append_row({
        "name":        data.get("name", ""),
        "phone":       data.get("phone", ""),
        "grade":       data.get("grade", ""),
        "district":    data.get("district", ""),
        "source":      data.get("source", "WebApp"),
        "telegram_id": user_id,
    })

    state_store.set_state(user_id, state_store.REGISTERED)

    # ReplyKeyboard ni yangilaymiz
    await message.answer("✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!", reply_markup=_build_main_reply_keyboard())

    # Keyin video menyuni chiqaramiz
    await message.answer(
        text=(
            "🎧 Qaysi darsni tinglamoqchisiz?\n\n"
            f"{_video_list_text()}"
        ),
        reply_markup=_build_video_menu(),
    )

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    try:
        # 1. Foydalanuvchi yuborgan ma'lumot xabarini o'chiramiz
        await message.delete()
        
        # 2. Bot yuborgan taklifnoma xabarini o'chiramiz
        reg_msg_id = state_store.get_metadata(user_id, "reg_message_id")
        if reg_msg_id:
            await message.bot.delete_message(message.chat.id, reg_msg_id)
    except Exception:
        pass


async def webapp_api_handler(request: web.Request, bot: Bot) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    user_id = data.get("user_id")
    if not user_id:
        return web.json_response({"ok": False, "error": "Missing user_id"}, status=400)

    sheets.append_row({
        "name":        data.get("name", ""),
        "phone":       data.get("phone", ""),
        "grade":       data.get("grade", ""),
        "district":    data.get("district", ""),
        "source":      data.get("source", "WebApp"),
        "telegram_id": user_id,
    })

    state_store.set_state(user_id, state_store.REGISTERED)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
                "🎧 Qaysi darsni tinglamoqchisiz?\n\n"
                f"{_video_list_text()}"
            ),
            reply_markup=_build_main_reply_keyboard(), # Bosh reply keyboard yuboramiz
        )
        await bot.send_message(
            chat_id=user_id,
            text="Pastdagi menyu orqali darslarni tanlashingiz mumkin:",
            reply_markup=_build_video_menu(),
        )
    except Exception as e:
        logger.error("Failed to send success message to user %s: %s", user_id, e)
        return web.json_response({"ok": False, "error": "Failed to send message"}, status=500)

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    reg_msg_id = data.get("message_id") or state_store.get_metadata(user_id, "reg_message_id")
    if reg_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=reg_msg_id)
        except Exception:
            pass

    return web.json_response({"ok": True})


def register_webapp_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(
        handle_web_app_data,
        content_types=types.ContentType.WEB_APP_DATA,
    )
