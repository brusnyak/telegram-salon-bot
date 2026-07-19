from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from config import load_config
from db.db import get_db


def is_admin(user_id: int) -> bool:
    cfg = load_config()
    return user_id == cfg.admin_chat_id


async def admin_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    async with get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT b.id, s.time, b.client_name, b.client_phone, sv.name
               FROM bookings b
               JOIN slots s ON b.slot_id = s.id
               JOIN services sv ON s.service_id = sv.id
               WHERE s.date = ? AND b.cancelled = 0
               ORDER BY s.time""",
            (today,),
        )

    if not rows:
        await update.message.reply_text("No bookings today.")
        return

    lines = [f"Bookings today ({today}):\n"]
    for r in rows:
        lines.append(f"{r[1]} - {r[2]} ({r[3]}) - {r[4]}")
    await update.message.reply_text("\n".join(lines))


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    async with get_db() as db:
        total = await db.execute_fetchall("SELECT COUNT(*) FROM bookings WHERE cancelled = 0")
        week = await db.execute_fetchall(
            """SELECT COUNT(*) FROM bookings b
               JOIN slots s ON b.slot_id = s.id
               WHERE s.date >= date('now', '-7 days') AND b.cancelled = 0"""
        )

    await update.message.reply_text(
        f"Stats:\n"
        f"- Total active bookings: {total[0][0]}\n"
        f"- Last 7 days: {week[0][0]}"
    )


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /admin_cancel <booking_id>")
        return

    booking_id = int(context.args[0])
    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT slot_id FROM bookings WHERE id = ? AND cancelled = 0", (booking_id,)
        )
        if not row:
            await update.message.reply_text("Booking does not exist or is already cancelled.")
            return

        slot_id = row[0][0]
        await db.execute("UPDATE bookings SET cancelled = 1 WHERE id = ?", (booking_id,))
        await db.execute("UPDATE slots SET booked = 0 WHERE id = ?", (slot_id,))
        await db.commit()

    await update.message.reply_text(f"Booking #{booking_id} cancelled and the slot is free again.")
