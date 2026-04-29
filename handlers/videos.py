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

    title      = video.get("title", f"Video {index}")
    url        = video.get("url", "").strip()
    video_path = video.get("video", "").strip()

    # ── Build caption ──────────────────────────────────────────────────────────
    caption = (
        f"📹 <b>{title}</b>\n"
        "——————————————————————\n"
        "Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?"
    )

    markup = _build_markup(url)

    # ── Resolve local video path ───────────────────────────────────────────────
    if video_path:
        abs_path = video_path if os.path.isabs(video_path) else os.path.join(BASE_DIR, video_path)
    else:
        abs_path = ""

    # ── Handle video sending ───────────────────────────────────────────────────
    if video_path:
        # 1-usul: Lokal fayl bo'lsa (serverda)
        if abs_path and os.path.exists(abs_path):
            try:
                with open(abs_path, "rb") as vf:
                    await callback.message.answer_video(
                        video=vf,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=markup,
                    )
                return
            except Exception:
                logger.exception("❌ Failed to send local video for index %s, falling back", index)
        # 2-usul: Agar file_id berilgan bo'lsa
        else:
            try:
                await callback.message.answer_video(
                    video=video_path,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
                return
            except Exception:
                logger.exception("❌ Failed to send video using file_id for index %s, falling back", index)

    # ── Fallback: text message with inline buttons ─────────────────────────────
    await callback.message.answer(
        caption,
        parse_mode="HTML",
        reply_markup=markup,
    )

async def get_video_file_id(message: types.Message) -> None:
    """Yangi videoni file_id orqali olish."""
    file_id = message.video.file_id
    await message.reply(
        f"✅ Bu videoning maxsus kodi (file_id):\n\n`{file_id}`\n\n"
        f"Uni shunchaki nusxalab oling va `.env` faylga xuddi shu tarzda joylang:\n"
        f'`VIDEO_1={{"video": "{file_id}", "title": "Dars nomi", "url": "..."}}`',
        parse_mode="Markdown"
    )


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
    # Register the utility handler for videos
    dp.register_message_handler(
        get_video_file_id,
        content_types=types.ContentType.VIDEO
    )
