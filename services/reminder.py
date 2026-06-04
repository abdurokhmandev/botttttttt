import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

REMINDER_DELAY = 10 * 60  # 10 minutes in seconds


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
    Sends a one-time reminder to STARTED users whose 10-minute window has elapsed.
    """
    now = time.time()
    all_users = state_store.get_all()

    for user_id, entry in all_users.items():
        if entry["state"] != state_store.STARTED:
            continue

        elapsed = now - entry["ts"]
        if elapsed < REMINDER_DELAY:
            continue

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "Suhbatlarimiz va darslarimiz sizga manzur bo'lmoqdami? 😊\n\n"
                    "Ularni to'liq tinglab borish va yangi suhbatlarni o'tkazib yubormaslik uchun "
                    "ro'yxatdan o'tishingizni iltimos qilamiz. Bu atigi 1 daqiqa vaqtingizni oladi ✨"
                ),
                reply_markup=_build_register_keyboard(),
            )
            state_store.set_state(user_id, state_store.REMINDER_SENT)
            logger.info("⏰ Reminder sent to user %s", user_id)
        except Exception as e:
            from aiogram.utils import exceptions
            if isinstance(e, (exceptions.BotBlocked, exceptions.UserDeactivated)):
                logger.warning("🚫 User %s has blocked the bot or account deleted. Skipping reminder.", user_id)
                state_store.set_metadata(user_id, "blocked", True)
            else:
                logger.error("❌ Failed to send reminder to user %s: %s", user_id, e)
