from telegram import Update
from telegram.ext import ContextTypes

from handlers.common import main_menu_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Demo Beauty Salon.\n\n"
        "I can help you book hair, nails, colouring, or massage appointments.",
        reply_markup=main_menu_keyboard(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_main":
        await query.edit_message_text(
            "Welcome to Demo Beauty Salon.\n\nChoose what you would like to do:",
            reply_markup=main_menu_keyboard(),
        )
    elif query.data == "about":
        await query.edit_message_text(
            "Demo Beauty Salon\n\n"
            "Phone: +421 900 123 456\n"
            "Address: Hlavna 15, Bratislava\n\n"
            "Opening hours:\n"
            "Monday-Friday: 10:00-18:00\n"
            "Saturday: 10:00-14:00",
            reply_markup=main_menu_keyboard(),
        )
