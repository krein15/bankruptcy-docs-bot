"""Настройки из файла .env. Секреты и всё, что отличается у разных фирм, — только там."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN не найден, проверьте файл .env")

# Telegram ID юристов через запятую: им приходят документы на проверку
LAWYER_IDS = {int(x) for x in os.getenv("LAWYER_IDS", "").replace(" ", "").split(",") if x}

DB_PATH = BASE_DIR / os.getenv("DB_PATH", "bot.db")

# Часовой пояс фирмы: по нему бот решает, что сейчас день, и показывает время юристу
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))

# Напоминания
REMIND_AFTER_HOURS = float(os.getenv("REMIND_AFTER_HOURS", "48"))  # клиент молчит столько часов
REMIND_MAX = int(os.getenv("REMIND_MAX", "5"))                     # не больше стольких напоминаний подряд
REMIND_FROM = int(os.getenv("REMIND_FROM", "10"))                  # напоминать только с 10:00
REMIND_TO = int(os.getenv("REMIND_TO", "20"))                      # и до 20:00
UNSUBMITTED_AFTER_MINUTES = float(os.getenv("UNSUBMITTED_AFTER_MINUTES", "30"))  # прислал файлы, но не нажал «Готово»
