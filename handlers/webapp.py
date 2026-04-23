import json
import logging

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS
from services import sheets
from storage import state_store

logger = logging.getLogger(__name__)


def _build_video_menu() -> InlineKeyboardMarkup:
    """Build the 5-button inline keyboard for video selection."""
    buttons = [
        InlineKeyboardButton(text=str(i), callback_data=f"video_{i}")
        for i in range(1, 6)
    ]
    # Row of 5 buttons
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

    # ── Save to Google Sheets ─────────────────────────────────────────────────
    sheets.append_row({
        "name":        data.get("name", ""),
        "phone":       data.get("phone", ""),
        "grade":       data.get("grade", ""),
        "district":    data.get("district", ""),
        "source":      data.get("source", ""),
        "telegram_id": user_id,
    })

    # ── Update state ──────────────────────────────────────────────────────────
    state_store.set_state(user_id, state_store.REGISTERED)

    source = data.get("source", "our platform")

    # ── Thank-you message + video menu ────────────────────────────────────────
    await message.answer(
        text=(
            f"Thank you for joining via *{source}*! 🎉\n\n"
            "Choose a free lesson below:\n\n"
            f"{_video_list_text()}"
        ),
        parse_mode="Markdown",
        reply_markup=_build_video_menu(),
    )


def register_webapp_handler(dp: Dispatcher) -> None:
    dp.register_message_handler(
        handle_web_app_data,
        content_types=types.ContentType.WEB_APP_DATA,
    )
