#!/usr/bin/env python3
"""
Telegram Salon Bot — appointment booking for Salón Kráľovná.

Run:
    TELEGRAM_BOT_TOKEN=... python -m main
"""
import logging
import sys

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from config import load_config
from db.db import init_db
from handlers.admin import admin_cancel, admin_stats, admin_today
from handlers.booking import expired_button, get_conv_handler
from handlers.start import menu_callback, start
from reminders import check_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


async def on_startup(app):
    await init_db()
    logger.info("Database initialized and seeded.")


def main():
    cfg = load_config()
    if not cfg.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    app = (
        ApplicationBuilder()
        .token(cfg.bot_token)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start", start))

    # Booking conversation flow
    app.add_handler(get_conv_handler())

    # Admin commands
    app.add_handler(CommandHandler("today", admin_today))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("admin_cancel", admin_cancel))

    # Menu / about callbacks (outside conversation)
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu_main|about)$"))
    app.add_handler(CallbackQueryHandler(expired_button, pattern="^(svc_|stf_|dt_|slot_|confirm_|back_)"))

    # Reminder job — check every 15 minutes
    app.job_queue.run_repeating(check_reminders, interval=900, first=30)

    logger.info("Salon bot started. Polling for updates...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
