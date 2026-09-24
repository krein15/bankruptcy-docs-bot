"""Точка входа. Запуск из папки проекта: python -m bot"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot import db, texts
from bot.checklist import CHECKLIST
from bot.config import BOT_TOKEN, LAWYER_IDS
from bot.handlers import client, lawyer


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not LAWYER_IDS:
        logging.warning("LAWYER_IDS пуст — документы на проверку никому не придут")

    db.init_db()
    logging.info("Документов в списке: %d, юристов: %d", len(CHECKLIST), len(LAWYER_IDS))

    # parse_mode=HTML — чтобы в текстах работали <b>жирный</b> и <i>курсив</i>
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in texts.COMMANDS])

    dp = Dispatcher()
    # Порядок важен: сначала роутер юриста, всё, что он не обработал, уходит клиентскому
    dp.include_routers(lawyer.router, client.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
