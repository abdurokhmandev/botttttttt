import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

REMINDER_DELAY = 10 * 60  # 10 minutes in seconds
SECOND_REMINDER_DELAY = 24 * 60 * 60  # 24 hours in seconds


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


async def check_reminders(bot: Bot) -> None:
    """
    Called by the APScheduler every minute.
    Sends reminders to users based on podcast selection time and first reminder time.
    """
    now = time.time()
    all_users = state_store.get_all()

    for user_id, entry in all_users.items():
        state = entry.get("state")

        # 1. First reminder (10 minutes after podcast selection)
        if state == "PODCAST_SELECTED":
            selected_ts = state_store.get_metadata(user_id, "podcast_selected_ts")
            if not selected_ts:
                selected_ts = entry.get("ts", now)

            elapsed = now - selected_ts
            if elapsed < REMINDER_DELAY:
                continue

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="Agar ro'yxatdan o'tsangiz sizga har hafta yangi podkastlar jo'natiladi",
                    reply_markup=_build_register_keyboard(),
                )
                state_store.set_state(user_id, "FIRST_REMINDER_SENT")
                state_store.set_metadata(user_id, "first_reminder_sent_ts", time.time())
                logger.info("⏰ First reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.utils import exceptions
                if isinstance(e, (exceptions.BotBlocked, exceptions.UserDeactivated)):
                    logger.warning("🚫 User %s has blocked the bot or account deleted. Skipping first reminder.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send first reminder to user %s: %s", user_id, e)

        # 2. Second reminder (24 hours after first reminder is sent)
        elif state == "FIRST_REMINDER_SENT":
            sent_ts = state_store.get_metadata(user_id, "first_reminder_sent_ts")
            if not sent_ts:
                sent_ts = entry.get("ts", now)

            elapsed = now - sent_ts
            if elapsed < SECOND_REMINDER_DELAY:
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
                state_store.set_state(user_id, "SECOND_REMINDER_SENT")
                logger.info("⏰ Second reminder (24h) sent to user %s", user_id)
            except Exception as e:
                from aiogram.utils import exceptions
                if isinstance(e, (exceptions.BotBlocked, exceptions.UserDeactivated)):
                    logger.warning("🚫 User %s has blocked the bot or account deleted. Skipping second reminder.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send second reminder to user %s: %s", user_id, e)
