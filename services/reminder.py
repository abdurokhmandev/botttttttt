import logging
import time

from aiogram import Bot

from storage import state_store

logger = logging.getLogger(__name__)

VIDEO_WATCH_DELAY     = 30 * 60       # 30 daqiqa (video ko'rish kutish)
SNOOZE_15_DELAY       = 15 * 60       # 15 daqiqa
SNOOZE_60_DELAY       = 60 * 60       # 1 soat
SNOOZE_TOMORROW_DELAY = 24 * 60 * 60  # 1 kun


async def check_reminders(bot: Bot) -> None:
    now = time.time()
    all_users = state_store.get_all()

    for user_id, entry in all_users.items():
        if entry.get("blocked"):
            continue

        if entry.get("state") == state_store.REGISTERED:
            if entry.get("funnel_state"):
                state_store.clear_funnel_progress(user_id)
            continue

        funnel_state = state_store.get_metadata(user_id, "funnel_state")

        # ── 1. Video ko'rish — 30 daqiqa kutish ──────────────────────────────
        if funnel_state == state_store.VIDEO_SENT:
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

        # ── 2. Snooze — 15 daqiqa ────────────────────────────────────────────
        elif funnel_state == state_store.SNOOZE_15:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_15_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-15 video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-15 user=%s: %s", user_id, e)

        # ── 3. Snooze — 1 soat ────────────────────────────────────────────────
        elif funnel_state == state_store.SNOOZE_60:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_60_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-60 video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-60 user=%s: %s", user_id, e)

        # ── 4. Snooze — ertaga ────────────────────────────────────────────────
        elif funnel_state == state_store.SNOOZE_TOMORROW:
            snooze_ts = state_store.get_metadata(user_id, "snooze_ts")
            if not snooze_ts or (now - snooze_ts) < SNOOZE_TOMORROW_DELAY:
                continue
            try:
                from handlers.funnel import _resend_last_video
                await _resend_last_video(bot, user_id)
                logger.info("⏰ Snooze-tomorrow video resent to user %s", user_id)
            except Exception as e:
                logger.error("❌ Snooze-tomorrow user=%s: %s", user_id, e)
