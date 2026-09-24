"""Напоминания клиентам. Планировщик (APScheduler) вызывает check_reminders раз в минуту."""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

from bot import db, keyboards as kb, texts
from bot.checklist import BY_ID, is_complete
from bot.config import REMIND_AFTER_HOURS, REMIND_FROM, REMIND_MAX, REMIND_TO, TIMEZONE, UNSUBMITTED_AFTER_MINUTES


def is_daytime() -> bool:
    """Ночью не напоминаем: считаем по часовому поясу фирмы."""
    return REMIND_FROM <= datetime.now(TIMEZONE).hour < REMIND_TO


async def _send(bot: Bot, client_id: int, text: str, markup: InlineKeyboardMarkup) -> bool:
    try:
        await bot.send_message(client_id, text, reply_markup=markup)
        return True
    except TelegramAPIError as e:  # например, клиент заблокировал бота
        logging.warning("Не удалось отправить напоминание клиенту %s: %s", client_id, e)
        return False


async def send_reminder(bot: Bot, client) -> bool:
    """«Осталось прислать: …». Вызывается планировщиком и кнопкой юриста «Напомнить»."""
    statuses = db.get_statuses(client["id"])
    sent = await _send(bot, client["id"], texts.reminder_text(statuses), kb.send_documents())
    # Отмечаем даже при ошибке: иначе будем пытаться достучаться до заблокировавшего бота каждую минуту
    db.mark_reminded(client["id"])
    return sent


async def remind_unsubmitted(bot: Bot) -> None:
    """Клиент прислал файлы, но не нажал «Готово» или не выбрал документ — юрист их не видит."""
    silent_since = datetime.now(timezone.utc) - timedelta(minutes=UNSUBMITTED_AFTER_MINUTES)
    by_client: dict[int, list] = {}
    for row in db.get_unsubmitted(silent_since):
        by_client.setdefault(row["client_id"], []).append(row)

    for client_id, rows in by_client.items():
        docs = [(row["doc_id"], row["files"]) for row in rows if row["doc_id"] in BY_ID]
        if docs:
            await _send(bot, client_id, texts.UNSUBMITTED, kb.unsubmitted(docs))
        if any(row["doc_id"] is None for row in rows):
            statuses = db.get_statuses(client_id)
            await _send(bot, client_id, texts.UNSORTED_REMINDER, kb.documents(statuses, action="assign"))
        db.mark_unsubmitted_reminded(client_id)
        logging.info("Напомнил клиенту %s отправить присланные файлы", client_id)


async def remind_silent(bot: Bot) -> None:
    """Клиент давно молчит, а документы собраны не все."""
    silent_since = datetime.now(timezone.utc) - timedelta(hours=REMIND_AFTER_HOURS)
    for client in db.get_clients_to_remind(silent_since, REMIND_MAX):
        if is_complete(db.get_statuses(client["id"])):
            continue
        await send_reminder(bot, client)
        logging.info("Напомнил клиенту %s про документы (%d-е подряд)", client["id"], client["reminders_sent"] + 1)


async def check_reminders(bot: Bot) -> None:
    if not is_daytime():
        return
    await remind_unsubmitted(bot)
    await remind_silent(bot)
