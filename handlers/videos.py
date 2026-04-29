import logging
import os

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS, BASE_DIR

logger = logging.getLogger(__name__)

# YouTube video ID dan thumbnail URL olish
def _yt_thumbnail(url: str) -> str:
    """YouTube URL dan maxresdefault thumbnail URL hosil qilish."""
    import re
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            vid_id = m.group(1)
            return f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
    return ""


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

    title = video.get("title", f"Video {index}")
    url   = video.get("url", "").strip()

    # ── Build caption ──────────────────────────────────────────────────────────
    caption = (
        f"📹 <b>{title}</b>\n"
        "——————————————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    )

    markup = _build_markup(url)

    # ── YouTube thumbnail orqali send_photo ────────────────────────────────────
    thumbnail_url = _yt_thumbnail(url) if url else ""

    if thumbnail_url:
        try:
            await callback.message.answer_photo(
                photo=thumbnail_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
            return
        except Exception:
            logger.exception("❌ Failed to send YouTube thumbnail for index %s, falling back", index)

    # ── Cover rasmidan foydalanish ─────────────────────────────────────────────
    cover_path = os.path.join(BASE_DIR, "static", "cover.png")
    if os.path.exists(cover_path):
        try:
            with open(cover_path, "rb") as cf:
                await callback.message.answer_photo(
                    photo=cf,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
            return
        except Exception:
            logger.exception("❌ Failed to send cover photo for index %s, falling back", index)

    # ── Oxirgi fallback: faqat matn ───────────────────────────────────────────
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
