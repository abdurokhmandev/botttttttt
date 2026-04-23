import logging

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS

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

    # ── 1. Send video (if file_id available) ─────────────────────────────────
    if file_id:
        try:
            await callback.message.answer_video(
                video=file_id,
                caption=f"📹 *{title}*",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("❌ Failed to send video file_id for video_%s", index)
            # Fall through to URL-only delivery
    else:
        await callback.message.answer(f"📹 *{title}*", parse_mode="Markdown")

    # ── 2. Send URL ───────────────────────────────────────────────────────────
    if url:
        await callback.message.answer(f"🔗 Watch here: {url}")

    # ── 3. School info button ─────────────────────────────────────────────────
    await callback.message.answer(
        "Want to know more about Rahimov School?",
        reply_markup=_build_school_button(),
    )


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
