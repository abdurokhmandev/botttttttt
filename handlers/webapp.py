import json
import logging

from aiogram import Dispatcher, types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
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

    # Avval ReplyKeyboard ni olib tashlaymiz
    await message.answer("✅", reply_markup=ReplyKeyboardRemove())

    # Keyin video menyuni chiqaramiz
    await message.answer(
        text=(
            "Ro'yxatdan o'tdingiz! 🎉\n\n"
            "Quyidagi bepul darslardan birini tanlang:\n\n"
            f"{_video_list_text()}"
        ),
        parse_mode="Markdown",
        reply_markup=_build_video_menu(),
    )

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
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
                "Ro'yxatdan o'tdingiz! 🎉\n\n"
                "Quyidagi bepul darslardan birini tanlang:\n\n"
                f"{_video_list_text()}"
            ),
            parse_mode="Markdown",
            reply_markup=_build_video_menu(),
        )
    except Exception as e:
        logger.error("Failed to send success message to user %s: %s", user_id, e)

    # Ro'yxatdan o'tish taklifnomasi xabarini o'chirish
    message_id = data.get("message_id")
    if message_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass

    return web.json_response({"ok": True})


def register_webapp_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(
        handle_web_app_data,
        content_types=types.ContentType.WEB_APP_DATA,
    )
