from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Back", callback_data=callback_data)]])


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Book appointment", callback_data="book")],
        [InlineKeyboardButton("Salon info", callback_data="about")],
    ])


def yes_no_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirm booking", callback_data="confirm_yes")],
        [InlineKeyboardButton("Edit details", callback_data="back_name")],
        [InlineKeyboardButton("Cancel", callback_data="confirm_no")],
    ])
