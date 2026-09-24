"""Точка входа. Запуск из папки проекта: python -m bot"""
import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import config, db, reminders, texts
from bot.checklist import CHECKLIST
from bot.config import BASE_DIR, BOT_TOKEN, LAWYER_IDS, REMIND_FROM, REMIND_TO, TIMEZONE
from bot.handlers import client, lawyer


async def set_commands(bot: Bot) -> None:
    """Меню команд: клиенты видят свои, юристы — ещё и /clients, /export. В демо все видят всё."""
    default = texts.DEMO_COMMANDS if config.DEMO_MODE else texts.COMMANDS
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in default])
    # Личное меню юристов Telegram хранит отдельно — перезаписываем и его, иначе в демо осталось бы старое
    personal = texts.DEMO_COMMANDS if config.DEMO_MODE else texts.LAWYER_COMMANDS
    lawyer_commands = [BotCommand(command=c, description=d) for c, d in personal]
    for lawyer_id in LAWYER_IDS:
        try:
            await bot.set_my_commands(lawyer_commands, scope=BotCommandScopeChat(chat_id=lawyer_id))
        except TelegramAPIError as e:  # юрист ещё ни разу не открывал бота
            logging.warning("Не удалось настроить меню юриста %s: %s", lawyer_id, e)


async def set_description(bot: Bot) -> None:
    """Текст в пустом чате до «Начать» и в профиле бота — из texts.py, чтобы менять под фирму вместе с остальным."""
    demo = config.DEMO_MODE
    try:
        await bot.set_my_description(texts.DEMO_DESCRIPTION if demo else texts.DESCRIPTION)
        await bot.set_my_short_description(texts.DEMO_SHORT_DESCRIPTION if demo else texts.SHORT_DESCRIPTION)
    except TelegramAPIError as e:  # не критично: бот работает и без описания
        logging.warning("Не удалось обновить описание бота: %s", e)


async def main() -> None:
    # Лог и в окно, и в файл bot.log: по файлу потом видно, что происходило, когда окно уже закрыто.
    # Файл до 1 МБ, плюс 3 старых — чтобы лог не разрастался бесконечно
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(BASE_DIR / "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
        ],
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)  # иначе две строки в лог каждую минуту
    if config.DEMO_MODE:
        logging.warning("ДЕМО-РЕЖИМ: каждый посетитель сам себе юрист, автоматических напоминаний нет")
    elif not LAWYER_IDS:
        logging.warning("LAWYER_IDS пуст — документы на проверку никому не придут")

    db.init_db()
    logging.info("Документов в списке: %d, юристов: %d", len(CHECKLIST), len(LAWYER_IDS))

    # parse_mode=HTML — чтобы в текстах работали <b>жирный</b> и <i>курсив</i>
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await set_commands(bot)
    await set_description(bot)

    # Раз в минуту проверяем, кому пора напомнить. Сами условия — в reminders.py
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(reminders.check_reminders, "interval", minutes=1, kwargs={"bot": bot})
    scheduler.start()
    logging.info("Напоминания: с %d:00 до %d:00 (%s)", REMIND_FROM, REMIND_TO, TIMEZONE)

    dp = Dispatcher()
    # Порядок важен: сначала роутер юриста, всё, что он не обработал, уходит клиентскому
    dp.include_routers(lawyer.router, client.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
