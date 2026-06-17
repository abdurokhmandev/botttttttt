import logging
import os

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS, BASE_DIR
from storage import video_stats

logger = logging.getLogger(__name__)

# In-memory cache for file_ids to speed up delivery
# { 'photo_path': 'file_id' }
FILE_ID_CACHE: dict[str, str] = {}


def _build_markup(url: str) -> InlineKeyboardMarkup:
    """Two inline buttons: YouTube link + school info."""
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text="📼 YouTube'da ko'rish", url=url)])
    rows.append([InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def handle_video_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()

    try:
        index = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        logger.warning("Unexpected callback data: %s", callback.data)
        return

    # 📊 Statistikaga qo'shamiz
    video_stats.increment(index)

    video_data = VIDEOS.get(index)
    if not video_data:
        await callback.message.answer("⚠️ Video topilmadi.")
        return

    title      = video_data.get("title", f"Dars {index}")
    description = video_data.get("description", "").strip()
    url        = video_data.get("url", "").strip()
    video_path = video_data.get("video", "").strip()
    photo_path = video_data.get("photo", "").strip()

    caption = (
        f"<b>📹 {title}</b>\n\n"
        f"{description}\n"
        "————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    ) if description else (
        f"<b>📹 {title}</b>\n"
        "————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    )
    markup = _build_markup(url)

    # --- 1. Try sending VIDEO ---
    if video_path:
        # Check Cache
        cached_id = FILE_ID_CACHE.get(video_path)
        if cached_id:
            try:
                await callback.message.answer_video(video=cached_id, caption=caption, parse_mode="HTML", reply_markup=markup)
                return
            except Exception:
                FILE_ID_CACHE.pop(video_path, None)

        # Try sending as file or file_id
        try:
            if video_path.startswith(("http://", "https://")):
                msg = await callback.message.answer_video(video=video_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                abs_video = video_path if os.path.isabs(video_path) else os.path.join(BASE_DIR, video_path)
                if os.path.exists(abs_video):
                    from aiogram.types import InputFile
                    msg = await callback.message.answer_video(video=InputFile(abs_video), caption=caption, parse_mode="HTML", reply_markup=markup)
                else:
                    # Try as raw file_id
                    msg = await callback.message.answer_video(video=video_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            
            if msg.video:
                FILE_ID_CACHE[video_path] = msg.video.file_id
            return
        except Exception as e:
            logger.error("❌ Video yuborishda xatolik (index %d): %s", index, e)
            # Fall through to photo

    # --- 2. Fallback to PHOTO ---
    if photo_path:
        cached_id = FILE_ID_CACHE.get(photo_path)
        if cached_id:
            try:
                await callback.message.answer_photo(photo=cached_id, caption=caption, parse_mode="HTML", reply_markup=markup)
                return
            except Exception:
                FILE_ID_CACHE.pop(photo_path, None)

        try:
            if photo_path.startswith(("http://", "https://")):
                msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                abs_photo = photo_path if os.path.isabs(photo_path) else os.path.join(BASE_DIR, photo_path)
                if os.path.exists(abs_photo):
                    from aiogram.types import InputFile
                    msg = await callback.message.answer_photo(photo=InputFile(abs_photo), caption=caption, parse_mode="HTML", reply_markup=markup)
                else:
                    msg = await callback.message.answer_photo(photo=photo_path, caption=caption, parse_mode="HTML", reply_markup=markup)
            
            if msg.photo:
                FILE_ID_CACHE[photo_path] = msg.photo[-1].file_id
            return
        except Exception as e:
            logger.error("❌ Rasm yuborishda xatolik (index %d): %s", index, e)

    # --- 3. Final Fallback: Text only ---
    await callback.message.answer(caption, parse_mode="HTML", reply_markup=markup)


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
