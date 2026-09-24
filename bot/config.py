"""Настройки из файла .env. Секреты и всё, что отличается у разных фирм, — только там."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN не найден, проверьте файл .env")

# Telegram ID юристов через запятую: им приходят документы на проверку
LAWYER_IDS = {int(x) for x in os.getenv("LAWYER_IDS", "").replace(" ", "").split(",") if x}

DB_PATH = BASE_DIR / os.getenv("DB_PATH", "bot.db")
