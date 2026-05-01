import asyncio
import logging

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from handlers.start  import register_start_handler
from handlers.webapp import register_webapp_handler, webapp_api_handler
from handlers.videos import register_video_handlers
from handlers.school import register_school_handler
from handlers.admin import register_admin_handlers
from services.reminder import check_reminders

import os
from aiohttp import web
import aiohttp_cors

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
register_admin_handlers(dp)


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

    # ── Start Web Server for WebApp API ───────────────────────────────────────────
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,   # Must be False when allow_origin="*"
            expose_headers="*",
            allow_headers="*",
            allow_methods=["POST", "OPTIONS"],  # iOS preflight requires this
        )
    })

    # Wrap the handler so it can access the bot object
    async def handler_wrapper(request):
        return await webapp_api_handler(request, bot)

    app.router.add_post('/api/submit', handler_wrapper)

    for route in list(app.router.routes()):
        cors.add(route)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Web server for WebApp started on port {port}.")


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
    )
