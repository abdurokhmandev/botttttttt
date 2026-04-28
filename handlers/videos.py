import logging

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import VIDEOS

logger = logging.getLogger(__name__)


def _build_school_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")
    ]])


def _build_youtube_button(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Youtube'da ko'ring", url=url)],
        [InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")],
    ])


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

    title = video.get("title", f"Video {index}")
    url   = video.get("url", "").strip()

    # ── Build message text ────────────────────────────────────────────────────
    lines = [f"📹 <b>{title}</b>"]
    lines.append("——————————————————————")
    lines.append("Rahimov School haqida ko'proq ma'lumot olishni xohlaysizmi?")
    text = "\n".join(lines)

    # ── Send inline button with YouTube link (no cover photo) ─────────────────
    if url:
        markup = _build_youtube_button(url)
    else:
        markup = _build_school_button()

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )


def register_video_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_video_callback,
        lambda c: c.data and c.data.startswith("video_"),
    )
