import logging
import os

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS, BASE_DIR

logger = logging.getLogger(__name__)


def _build_markup(url: str) -> InlineKeyboardMarkup:
    """Two inline buttons: YouTube link + school info."""
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="▶️ Youtube'da ko'ring", url=url)])
    rows.append([InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def handle_video_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()  # Remove loading spinner

    try:
        index = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        logger.warning("Unexpected callback data: %s", callback.data)
        return

    video = VIDEOS.get(index)
    if not video:
        await callback.message.answer("⚠️ Video topilmadi.")
        return

    title      = video.get("title", f"Dars {index}")
    url        = video.get("url", "").strip()
    photo_path = video.get("photo", "").strip() or video.get("video", "").strip()

    # ── Build caption ──────────────────────────────────────────────────────────
    caption = (
        f"🖼️ <b>{title}</b>\n"
        "——————————————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    )

    markup = _build_markup(url)

    # ── Send photo (from URL, local file, or file_id) ──────────────────────────
    if not photo_path:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=markup)
        return

    # 1. Try URL
    if photo_path.startswith(("http://", "https://")):
        try:
            await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            logger.exception("❌ Failed to send photo URL for index %s", index)

    # 2. Try Local File
    abs_path = photo_path if os.path.isabs(photo_path) else os.path.join(BASE_DIR, photo_path)
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        try:
            with open(abs_path, "rb") as pf:
                await callback.message.answer_photo(photo=pf, caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            logger.exception("❌ Failed to send local photo for index %s", index)

    # 3. Try as file_id (as last resort)
    try:
        await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
        return
    except Exception:
        logger.exception("❌ Failed to send photo as file_id for index %s", index)

    # ── Fallback: text message ─────────────────────────────────────────────────
    await callback.message.answer(
        caption,
        parse_mode="HTML",
        reply_markup=markup,
    )


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
