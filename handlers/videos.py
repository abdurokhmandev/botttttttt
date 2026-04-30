import logging
import os

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS, BASE_DIR

logger = logging.getLogger(__name__)

# In-memory cache for file_ids to speed up delivery
# { 'photo_path': 'file_id' }
FILE_ID_CACHE: dict[str, str] = {}


def _build_markup(url: str) -> InlineKeyboardMarkup:
    """Two inline buttons: YouTube link + school info."""
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="📹 Videoni ko'rish", url=url)])
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
        f"<b>{title}</b>\n"
        "————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    )

    markup = _build_markup(url)

    # ── Send photo (from URL, local file, or file_id) ──────────────────────────
    if not photo_path:
        await callback.message.answer(caption, parse_mode="HTML", reply_markup=markup)
        return

    # 0. Try Cache (Speed Hack)
    cached_file_id = FILE_ID_CACHE.get(photo_path)
    if cached_file_id:
        try:
            await callback.message.answer_photo(
                photo=cached_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup
            )
            return
        except Exception:
            logger.warning("Cached file_id expired or invalid for %s", photo_path)
            FILE_ID_CACHE.pop(photo_path, None)

    # 1. Try URL
    if photo_path.startswith(("http://", "https://")):
        try:
            msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            if msg.photo:
                FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
            return
        except Exception as e:
            logger.error("❌ Failed to send photo URL for index %s: %s", index, e)

    # 2. Try Local File
    if os.path.isabs(photo_path):
        abs_path = photo_path
    else:
        abs_path = os.path.join(BASE_DIR, photo_path)
    
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        try:
            from aiogram.types import InputFile
            msg = await callback.message.answer_photo(
                photo=InputFile(abs_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup
            )
            if msg.photo:
                FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
            return
        except Exception as e:
            logger.error("❌ Error sending photo file %s: %s", abs_path, e)
    else:
        logger.warning("⚠️ Photo file NOT FOUND at: %s", abs_path)

    # 3. Try as file_id (as last resort)
    try:
        msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
        if msg.photo:
            FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
        return
    except Exception:
        pass

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
