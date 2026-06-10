import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

REMINDER_DELAY = 10 * 60
SECOND_REMINDER_DELAY = 24 * 60 * 60


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
    now = time.time()
    all_users = state_store.get_all()

    for user_id, entry in all_users.items():
        state = entry.get("state")
        logger.debug("Reminder check – user:%s state:%s", user_id, state)

        if state == state_store.PODCAST_SELECTED:
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
                state_store.set_state(user_id, state_store.FIRST_REMINDER_SENT)
                state_store.set_metadata(user_id, "first_reminder_sent_ts", time.time())
                logger.info("⏰ First reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.utils import exceptions
                if isinstance(e, (exceptions.BotBlocked, exceptions.UserDeactivated)):
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
                logger.info("⏰ Second reminder sent to user %s", user_id)
            except Exception as e:
                from aiogram.utils import exceptions
                if isinstance(e, (exceptions.BotBlocked, exceptions.UserDeactivated)):
                    logger.warning("🚫 User %s blocked or deleted. Skipping.", user_id)
                    state_store.set_metadata(user_id, "blocked", True)
                else:
                    logger.error("❌ Failed to send second reminder to user %s: %s", user_id, e)