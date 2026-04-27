import logging

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS, VIDEO_PHOTO

logger = logging.getLogger(__name__)


def _build_school_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏫 Learn about the school", callback_data="school_info")
    ]])


async def handle_video_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()  # Remove loading spinner

    try:
        index = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        logger.warning("Unexpected callback data: %s", callback.data)
        return

    video = VIDEOS.get(index)
    if not video:
        await callback.message.answer("⚠️ Video not found.")
        return

    title   = video.get("title", f"Video {index}")
    file_id = video.get("file_id", "").strip()
    url     = video.get("url", "").strip()

    # ── Build combined caption ────────────────────────────────────────────────
    lines = [f"📹 *{title}*"]
    lines.append("——————————————————————")
    if url:
        lines.append(f"🔗 Watch here: {url}")
        lines.append("——————————————————————")
    lines.append("Want to know more about Rahimov School?")

    caption = "\n".join(lines)

    # ── Send as ONE message with photo + inline button ────────────────────────
    photo = VIDEO_PHOTO.strip() if VIDEO_PHOTO else ""

    if photo:
        try:
            await callback.message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=_build_school_button(),
            )
            return
        except Exception:
            logger.exception("❌ Failed to send photo, falling back to text")

    # Fallback: send as plain text if no photo or photo failed
    await callback.message.answer(
        caption,
        parse_mode="Markdown",
        reply_markup=_build_school_button(),
    )


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
