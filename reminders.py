import logging
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from db.db import get_db

logger = logging.getLogger(__name__)


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Job: check upcoming bookings and send reminders 2h before."""
    now = datetime.now(timezone.utc)

    async with get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT b.id, b.client_name, s.time, sv.name, s.id
               FROM bookings b
               JOIN slots s ON b.slot_id = s.id
               JOIN services sv ON s.service_id = sv.id
               WHERE s.date = ? AND b.reminded = 0 AND b.cancelled = 0""",
            (now.date().isoformat(),),
        )

        updated_ids = []
        for r in rows:
            booking_id, name, slot_time, service_name, slot_id = r
            hour, minute = map(int, slot_time.split(":"))
            booking_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            diff_min = (booking_dt - now).total_seconds() / 60

            if 110 <= diff_min <= 130:
                text = (
                    f"Appointment reminder: booking starts in about 2 hours.\n\n"
                    f"Client: {name}\n"
                    f"Service: {service_name}\n"
                    f"Time: {slot_time}"
                )
                try:
                    from config import load_config
                    cfg = load_config()
                    await context.bot.send_message(chat_id=cfg.admin_chat_id, text=text)
                except Exception as exc:
                    logger.warning("Failed to send reminder for booking %s: %s", booking_id, exc)

            updated_ids.append(booking_id)

        if updated_ids:
            for bid in updated_ids:
                await db.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (bid,))
            await db.commit()
