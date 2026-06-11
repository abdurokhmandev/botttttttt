import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

REMINDER_DELAY        = 10 * 60       # 10 daqiqa (birinchi eslatma)
SECOND_REMINDER_DELAY = 24 * 60 * 60  # 24 soat
THIRD_REMINDER_DELAY  = 48 * 60 * 60  # 48 soat
VIDEO_WATCH_DELAY     = 30 * 60       # 30 daqiqa (video ko'rish kutish)
SNOOZE_15_DELAY       = 15 * 60       # 15 daqiqa
SNOOZE_60_DELAY       = 60 * 60       # 1 soat
SNOOZE_TOMORROW_DELAY = 24 * 60 * 60  # 1 kun


def _build_register_keyboard() -> InlineKeyboardMarkup:
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Ro'yxatdan o'tish",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📝 Ro'yxatdan o'tish",
                callback_data="start_registration",
            )
        ]])


def _eligible_for_first_reminder(state: str | None) -> bool:
    return state in (state_store.PODCAST_SELECTED, state_store.STARTED)


async def check_reminders(bot: Bot) -> None:
    now = time.time()
    all_users = state_store.get_all()
    pending_first = pending_second = pending_third = 0

    for user_id, entry in all_users.items():
        if entry.get("blocked"):
            continue

        state = entry.get("state")

        # ── 1. Eski eslatmalar (ro'yxatdan o'tmagan) ─────────────────────────
        if _eligible_for_first_reminder(state):
            if state == state_store.STARTED and not state_store.get_metadata(user_id, "podcast_selected_ts"):
                continue
            selected_ts = state_store.get_metadata(user_id, "podcast_selected_ts")
            if not selected_ts:
                selected_ts = entry.get("ts", now)

            elapsed = now - selected_ts
            if elapsed < REMINDER_DELAY:
                pending_first += 1
                continue

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="Agar ro'yxatdan o'tsangiz sizga har hafta yangi podkastlar jo'natiladi",
                    reply_markup=_build_register_keyboard(),
                )
                state_store.set_state(user_id, state_store.FIRST_REMINDER_SENT)
                state_store.set_metadata(user_id, "first_reminder_sent_ts", time.time())
                logger.info("⏰ First reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.exceptions import TelegramForbiddenError
                if isinstance(e, TelegramForbiddenError):
                    logger.warning("🚫 User %s blocked or deleted. Skipping.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send first reminder to user %s: %s", user_id, e)

        elif state == state_store.FIRST_REMINDER_SENT:
            sent_ts = state_store.get_metadata(user_id, "first_reminder_sent_ts")
            if not sent_ts:
                sent_ts = entry.get("ts", now)

            elapsed = now - sent_ts
            if elapsed < SECOND_REMINDER_DELAY:
                pending_second += 1
                continue

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "Hurmatli foydalanuvchi, dars va suhbatlarimizdan to'liq foydalanish hamda "
                        "kelgusi darslarni o'tkazib yubormaslik uchun iltimos, ro'yxatdan o'ting. "
                        "Bu biz uchun juda muhim! 😊"
                    ),
                    reply_markup=_build_register_keyboard(),
                )
                state_store.set_state(user_id, state_store.SECOND_REMINDER_SENT)
                state_store.set_metadata(user_id, "second_reminder_sent_ts", time.time())
                logger.info("⏰ Second reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.exceptions import TelegramForbiddenError
                if isinstance(e, TelegramForbiddenError):
                    logger.warning("🚫 User %s blocked or deleted. Skipping.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send second reminder to user %s: %s", user_id, e)

        elif state == state_store.SECOND_REMINDER_SENT:
            sent_ts = state_store.get_metadata(user_id, "second_reminder_sent_ts")
            if not sent_ts:
                sent_ts = entry.get("ts", now)

            elapsed = now - sent_ts
            if elapsed < THIRD_REMINDER_DELAY:
                pending_third += 1
                continue

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "Assalomu alaykum! Ro'yxatdan o'tib, "
                        "barcha dars va podkastlardan bepul foydalaning. "
                        "Kech qolmang! 🎯"
                    ),
                    reply_markup=_build_register_keyboard(),
                )
                state_store.set_state(user_id, state_store.THIRD_REMINDER_SENT)
                state_store.set_metadata(user_id, "third_reminder_sent_ts", time.time())
                logger.info("⏰ Third reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.exceptions import TelegramForbiddenError
                if isinstance(e, TelegramForbiddenError):
                    logger.warning("🚫 User %s blocked or deleted. Skipping.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send third reminder to user %s: %s", user_id, e)

        # ── 2. Video ko'rish — 30 daqiqa kutish ──────────────────────────────
        elif state == state_store.VIDEO_SENT:
            sent_ts = state_store.get_metadata(user_id, "video_sent_ts")
            if not sent_ts:
                continue
            elapsed = now - sent_ts
            if elapsed < VIDEO_WATCH_DELAY:
                continue
            try:
                from handlers.funnel import send_watched_question
                await send_watched_question(bot, user_id)
                logger.info("⏰ Watched question sent to user %s", user_id)
            except Exception as e:
                logger.error("❌ send_watched_question user=%s: %s", user_id, e)

        # ── 3. Snooze — 15 daqiqa ────────────────────────────────────────────
        elif state == state_store.SNOOZE_15:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_15_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-15 video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-15 user=%s: %s", user_id, e)

        # ── 4. Snooze — 1 soat ────────────────────────────────────────────────
        elif state == state_store.SNOOZE_60:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_60_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-60 video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-60 user=%s: %s", user_id, e)

        # ── 5. Snooze — ertaga ────────────────────────────────────────────────
        elif state == state_store.SNOOZE_TOMORROW:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_TOMORROW_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-tomorrow video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-tomorrow user=%s: %s", user_id, e)

        # ── 6. "Yoqdimi?" savoli yuborildi — WANT_MORE holatida ──────────────
        elif state == state_store.WANT_MORE_ASKED:
            # Foydalanuvchi podkast tanlashini kutmoqdamiz — boshqa amal yo'q
            pass

        # ── 7. Ro'yxatdan o'tish holati — kutish ─────────────────────────────
        elif state == state_store.REGISTER_OFFERED:
            pass

    if pending_first or pending_second or pending_third:
        logger.info(
            "⏳ Reminder queue: %d waiting for 10 min, %d waiting for 24 h, %d waiting for 48 h",
            pending_first,
            pending_second,
            pending_third,
        )
