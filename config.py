import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


@dataclass
class Config:
    bot_token: str
    admin_chat_id: int
    bot_ops_webhook: str | None
    salon_timezone: str
    booking_buffer_min: int


def load_config() -> Config:
    return Config(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        admin_chat_id=int(os.environ.get("ADMIN_CHAT_ID", "0")),
        bot_ops_webhook=os.environ.get("BOT_OPS_WEBHOOK_URL") or None,
        salon_timezone=os.environ.get("SALON_TIMEZONE", "Europe/Bratislava"),
        booking_buffer_min=int(os.environ.get("BOOKING_BUFFER_MIN", "15")),
    )
