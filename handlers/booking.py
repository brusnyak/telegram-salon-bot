import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from config import load_config
from db.db import get_db
from ops_webhook import send_to_ops_lab
from handlers.common import back_button, main_menu_keyboard, yes_no_keyboard

logger = logging.getLogger(__name__)

SELECT_SERVICE, SELECT_STAFF, SELECT_DATE, SELECT_SLOT, COLLECT_NAME, COLLECT_PHONE, CONFIRM = range(7)
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
STAFF_PHOTOS = {
    1: ASSET_DIR / "stylist-lucia.jpg",
    2: ASSET_DIR / "stylist-martina.jpg",
}


def _salon_now():
    cfg = load_config()
    try:
        tz = ZoneInfo(cfg.salon_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown SALON_TIMEZONE=%s, using Europe/Bratislava", cfg.salon_timezone)
        tz = ZoneInfo("Europe/Bratislava")
    return datetime.now(tz)


def _slot_is_bookable_today(slot_time: str) -> bool:
    import datetime as dt

    cfg = load_config()
    now = _salon_now()
    cutoff = now + dt.timedelta(minutes=cfg.booking_buffer_min)
    try:
        hour, minute = [int(part) for part in slot_time.split(":", 1)]
    except ValueError:
        return False
    slot_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot_dt > cutoff


async def book_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — show services."""
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT id, name, price_eur FROM services ORDER BY id")

    keyboard = [
        [InlineKeyboardButton(f"{r[1]} — €{r[2]:.0f}", callback_data=f"svc_{r[0]}")]
        for r in rows
    ]
    keyboard.append([InlineKeyboardButton("← Back", callback_data="menu_main")])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Choose a service:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "Choose a service:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
    return SELECT_SERVICE


async def service_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service_id = int(query.data.split("_")[1])
    context.user_data["service_id"] = service_id
    await show_staff(query, context)
    return SELECT_STAFF


async def show_staff(query, context: ContextTypes.DEFAULT_TYPE):
    service_id = context.user_data["service_id"]

    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT id, name FROM staff WHERE services LIKE ?",
            (f"%{service_id}%",),
        )

    keyboard = [
        [InlineKeyboardButton(r[1], callback_data=f"stf_{r[0]}")] for r in rows
    ]
    keyboard.append([InlineKeyboardButton("← Back", callback_data="back_services")])
    await query.edit_message_text(
        "Choose a staff member:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def staff_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["staff_id"] = int(query.data.split("_")[1])
    await show_staff_photo(query, context.user_data["staff_id"])
    await show_dates(query)
    return SELECT_DATE


async def show_dates(query):

    import datetime

    today = _salon_now().date()
    keyboard = []
    for i in range(7):
        d = today + datetime.timedelta(days=i)
        label = d.strftime("%a %d.%m.") if i > 0 else f"Today {d.strftime('%d.%m.')}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"dt_{d.isoformat()}")])

    keyboard.append([InlineKeyboardButton("← Back", callback_data="back_staff")])
    await query.edit_message_text(
        "Choose a date:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_staff_photo(query, staff_id: int):
    photo_path = STAFF_PHOTOS.get(staff_id)
    if not photo_path or not photo_path.exists():
        return
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT name FROM staff WHERE id = ?", (staff_id,))
    staff_name = row[0][0] if row else "Selected stylist"
    with photo_path.open("rb") as photo:
        await query.message.reply_photo(photo=photo, caption=f"You selected {staff_name}.")


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_", 1)[1]
    context.user_data["booking_date"] = date_str
    await show_slots(query, context)
    return SELECT_SLOT


async def show_slots(query, context: ContextTypes.DEFAULT_TYPE):
    date_str = context.user_data["booking_date"]
    service_id = context.user_data["service_id"]
    staff_id = context.user_data["staff_id"]

    async with get_db() as db:
        rows = await db.execute_fetchall(
            """SELECT id, time FROM slots
               WHERE staff_id = ? AND service_id = ? AND date = ? AND booked = 0
               ORDER BY time""",
            (staff_id, service_id, date_str),
        )

    today = _salon_now().date().isoformat()
    if date_str == today:
        rows = [row for row in rows if _slot_is_bookable_today(row[1])]

    if not rows:
        message = "There are no free slots on this date. Please choose another date."
        if date_str == today:
            message = "There are no remaining bookable slots today. Please choose another date."
        await query.edit_message_text(
            message,
            reply_markup=back_button("back_dates"),
        )
        return SELECT_DATE

    keyboard = [
        [InlineKeyboardButton(r[1], callback_data=f"slot_{r[0]}")] for r in rows
    ]
    keyboard.append([InlineKeyboardButton("← Back", callback_data="back_dates")])
    await query.edit_message_text(
        "Choose a time:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def slot_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["slot_id"] = int(query.data.split("_")[1])
    await query.edit_message_text(
        "What name should I put on the booking?",
        reply_markup=back_button("back_slots"),
    )
    return COLLECT_NAME


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_name"] = update.message.text.strip()
    await update.message.reply_text(
        "What phone number should the salon use if they need to contact you?",
        reply_markup=back_button("back_name"),
    )
    return COLLECT_PHONE


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_phone"] = update.message.text.strip()
    ud = context.user_data

    async with get_db() as db:
        service = await db.execute_fetchall(
            "SELECT name, price_eur FROM services WHERE id = ?", (ud["service_id"],)
        )
        staff = await db.execute_fetchall(
            "SELECT name FROM staff WHERE id = ?", (ud["staff_id"],)
        )
        slot_info = await db.execute_fetchall(
            "SELECT time FROM slots WHERE id = ?", (ud["slot_id"],)
        )

    service_name = service[0][0] if service else "?"
    staff_name = staff[0][0] if staff else "?"
    slot_time = slot_info[0][0] if slot_info else "?"
    price = service[0][1] if service else 0

    summary = (
        f"Please confirm the booking:\n\n"
        f"Name: {ud['client_name']}\n"
        f"Phone: {ud['client_phone']}\n"
        f"Service: {service_name}\n"
        f"Staff: {staff_name}\n"
        f"Date: {ud['booking_date']}\n"
        f"Time: {slot_time}\n"
        f"Price: EUR {price:.0f}\n\n"
        f"Should I confirm it?"
    )
    await update.message.reply_text(summary, reply_markup=yes_no_keyboard())
    return CONFIRM


async def back_to_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await book_start(update, context)


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "Welcome to Salón Kráľovná.\n\nChoose what you want to do:",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def back_to_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "service_id" not in context.user_data:
        return await book_start(update, context)
    await show_staff(query, context)
    return SELECT_STAFF


async def back_to_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if "staff_id" not in context.user_data:
        return await back_to_staff(update, context)
    await show_dates(query)
    return SELECT_DATE


async def back_to_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    required = {"service_id", "staff_id", "booking_date"}
    if not required.issubset(context.user_data):
        return await back_to_dates(update, context)
    await show_slots(query, context)
    return SELECT_SLOT


async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("client_name", None)
    await query.edit_message_text(
        "What name should I put on the booking?",
        reply_markup=back_button("back_slots"),
    )
    return COLLECT_NAME


async def expired_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "This booking screen is no longer active. Please tap Book appointment to start again.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Book appointment", callback_data="book")]]),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text(
            "Booking cancelled. If you want to try again later, send /start.",
            reply_markup=None,
        )
        context.user_data.clear()
        return ConversationHandler.END

    ud = context.user_data
    slot_id = ud["slot_id"]

    async with get_db() as db:
        slot = await db.execute_fetchall(
            "SELECT booked FROM slots WHERE id = ?", (slot_id,)
        )
        if not slot or slot[0][0] != 0:
            await query.edit_message_text(
                "Sorry, that slot has just been taken. Please choose another slot.",
                reply_markup=None,
            )
            context.user_data.clear()
            return ConversationHandler.END

        await db.execute(
            "UPDATE slots SET booked = 1 WHERE id = ?", (slot_id,)
        )
        await db.execute(
            "INSERT INTO bookings (slot_id, client_name, client_phone) VALUES (?, ?, ?)",
            (slot_id, ud["client_name"], ud["client_phone"]),
        )
        await db.commit()

    await query.edit_message_text(
        "Booking confirmed.\n\n"
        "You will receive a reminder 2 hours before the appointment. "
        "If you need to cancel, contact the salon.",
        reply_markup=None,
    )

    # Push event to ops-lab dashboard
    cfg = load_config()
    if cfg.bot_ops_webhook:
        send_to_ops_lab(
            webhook_url=cfg.bot_ops_webhook,
            event_id=f"booking_{slot_id}_{datetime.now(timezone.utc).timestamp()}",
            sender_name=ud["client_name"],
            sender_handle=f"booking_{ud['client_phone']}",
            message=f"New booking: {ud['client_name']} - service {slot_id}, "
                    f"date {ud['booking_date']}, phone: {ud['client_phone']}",
        )

    # Schedule reminder (handled via JobQueue in main.py)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Booking cancelled.", reply_markup=None
        )
    elif update.message:
        await update.message.reply_text("Booking cancelled.")
    context.user_data.clear()
    return ConversationHandler.END


def get_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(book_start, pattern="^book$"),
            CommandHandler("book", book_start),
        ],
        states={
            SELECT_SERVICE: [
                CallbackQueryHandler(service_selected, pattern=r"^svc_"),
                CallbackQueryHandler(back_to_main, pattern=r"^menu_main$"),
            ],
            SELECT_STAFF: [
                CallbackQueryHandler(staff_selected, pattern=r"^stf_"),
                CallbackQueryHandler(back_to_services, pattern=r"^back_services$"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(date_selected, pattern=r"^dt_"),
                CallbackQueryHandler(back_to_staff, pattern=r"^back_staff$"),
            ],
            SELECT_SLOT: [
                CallbackQueryHandler(slot_selected, pattern=r"^slot_"),
                CallbackQueryHandler(back_to_dates, pattern=r"^back_dates$"),
            ],
            COLLECT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_received),
                CallbackQueryHandler(back_to_slots, pattern=r"^back_slots$"),
            ],
            COLLECT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received),
                CallbackQueryHandler(back_to_name, pattern=r"^back_name$"),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_handler, pattern=r"^confirm_"),
                CallbackQueryHandler(back_to_name, pattern=r"^back_name$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(back_to_services, pattern=r"^back_services$"),
            CallbackQueryHandler(back_to_staff, pattern=r"^back_staff$"),
            CallbackQueryHandler(back_to_dates, pattern=r"^back_dates$"),
            CallbackQueryHandler(back_to_slots, pattern=r"^back_slots$"),
            CallbackQueryHandler(back_to_name, pattern=r"^back_name$"),
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )
