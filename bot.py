import asyncio
import logging

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from handlers.start  import register_start_handler
from handlers.webapp import register_webapp_handler
from handlers.videos import register_video_handlers
from handlers.school import register_school_handler
from services.reminder import check_reminders

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot & Dispatcher ──────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN, parse_mode=None)
dp  = Dispatcher(bot, storage=MemoryStorage())

# ── Register Handlers ─────────────────────────────────────────────────────────
register_webapp_handler(dp)   # WebApp data — eng birinchi (state='*' bilan)
register_start_handler(dp)
register_video_handlers(dp)
register_school_handler(dp)


# ── Scheduler ─────────────────────────────────────────────────────────────────
async def on_startup(dispatcher: Dispatcher) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_reminders,
        trigger="interval",
        minutes=5,
        kwargs={"bot": bot},
        id="reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("✅ Bot started. Reminder scheduler running every 5 minutes.")


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
    )
