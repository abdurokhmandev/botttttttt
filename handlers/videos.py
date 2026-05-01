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

    # ── Media Handling (Video or Photo) ────────────────────────────────────────
    video_path = video.get("video", "").strip()
    photo_path = video.get("photo", "").strip()
    
    # 0. Try Cache first (for either video or photo)
    media_key = video_path or photo_path
    cached_file_id = FILE_ID_CACHE.get(media_key)
    if cached_file_id:
        try:
            if video_path:
                await callback.message.answer_video(video=cached_file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                await callback.message.answer_photo(photo=cached_file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:
            logger.warning("Cached file_id expired for %s", media_key)
            FILE_ID_CACHE.pop(media_key, None)

    # 1. Handle Video
    if video_path:
        # Check if it's a file_id or URL or local path
        if video_path.startswith(("http://", "https://")):
            try:
                msg = await callback.message.answer_video(video=video_path, caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.video: FILE_ID_CACHE[video_path] = msg.video.file_id
                return
            except Exception as e:
                logger.error("❌ Failed to send video URL: %s", e)
        
        # Local file
        abs_video = video_path if os.path.isabs(video_path) else os.path.join(BASE_DIR, video_path)
        if os.path.exists(abs_video) and os.path.isfile(abs_video):
            try:
                from aiogram.types import InputFile
                msg = await callback.message.answer_video(video=InputFile(abs_video), caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.video: FILE_ID_CACHE[video_path] = msg.video.file_id
                return
            except Exception as e:
                logger.error("❌ Error sending video file: %s", e)
        else:
            # Maybe it's a file_id
            try:
                msg = await callback.message.answer_video(video=video_path, caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.video: FILE_ID_CACHE[video_path] = msg.video.file_id
                return
            except Exception:
                pass

    # 2. Fallback to Photo (existing logic)
    if photo_path:
        if photo_path.startswith(("http://", "https://")):
            try:
                msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.photo: FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
                return
            except Exception as e:
                logger.error("❌ Failed to send photo URL: %s", e)

        abs_photo = photo_path if os.path.isabs(photo_path) else os.path.join(BASE_DIR, photo_path)
        if os.path.exists(abs_photo) and os.path.isfile(abs_photo):
            try:
                from aiogram.types import InputFile
                msg = await callback.message.answer_photo(photo=InputFile(abs_photo), caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.photo: FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
                return
            except Exception as e:
                logger.error("❌ Error sending photo file: %s", e)
        else:
            try:
                msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
                if msg.photo: FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
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
