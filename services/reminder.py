import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

REMINDER_DELAY = 15 * 60  # 15 minutes in seconds


def _build_register_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📝 Register",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])


async def check_reminders(bot: Bot) -> None:
    """
    Called by the APScheduler every 5 minutes.
    Sends a one-time reminder to STARTED users whose 24h window has elapsed.
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
                    "👋 Hey! You haven't finished registering yet.\n\n"
                    "Complete the form to access your free lessons 👇"
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
