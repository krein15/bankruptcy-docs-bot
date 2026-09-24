"""Общая обвязка тестов: подставной Telegram вместо настоящего.

Бот думает, что общается с Telegram, а на самом деле все его запросы — «отправить сообщение»,
«убрать кнопки», «переслать файл» — складываются в список. Тест пишет боту от имени пользователя,
жмёт кнопки и проверяет, что бот ответил и что записал в базу.
"""
import itertools
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

# Настройки задаём до импорта бота: config.py читает их при импорте.
# Заданное здесь важнее .env, поэтому тесты не зависят от твоих локальных настроек,
# а на GitHub, где .env нет, работают так же.
os.environ.update({
    "BOT_TOKEN": "123456:TEST",
    "LAWYER_IDS": "500",
    "DB_PATH": str(Path(tempfile.mkdtemp()) / "import.db"),
    "TIMEZONE": "Europe/Moscow",
    "REMIND_AFTER_HOURS": "48",
    "REMIND_MAX": "5",
    "REMIND_FROM": "10",
    "REMIND_TO": "20",
    "UNSUBMITTED_AFTER_MINUTES": "30",
    "DEMO_MODE": "false",  # демо включают отдельные тесты в test_demo.py
})

import pytest  # noqa: E402
from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.exceptions import TelegramForbiddenError  # noqa: E402
from aiogram.filters.callback_data import CallbackData  # noqa: E402
from aiogram.methods import AnswerCallbackQuery, SendMediaGroup  # noqa: E402
from aiogram.types import Message, Update  # noqa: E402

from bot import db, keyboards as kb, reminders  # noqa: E402
from bot.handlers import client, lawyer  # noqa: E402

LAWYER_ID = 500
LONG_AGO = "2020-01-01T00:00:00+00:00"  # «давно» — для проверки напоминаний
_ids = itertools.count(1000)


class FakeTelegram(BaseSession):
    """Вместо HTTP-запросов к Telegram складывает их в requests и отвечает правдоподобно."""

    def __init__(self):
        super().__init__()
        self.requests = []
        self.blocked: set[int] = set()  # пользователи, которые «заблокировали бота»

    async def make_request(self, bot, method, timeout=None):
        if getattr(method, "chat_id", None) in self.blocked:
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        self.requests.append(method)
        if type(method).__name__ in ("SendMessage", "SendPhoto", "SendDocument"):
            return Message.model_validate({
                "message_id": next(_ids),
                "date": int(time.time()),
                "chat": {"id": method.chat_id, "type": "private"},
                "text": getattr(method, "text", None) or "файл",
            }, context={"bot": bot})
        if isinstance(method, SendMediaGroup):
            return []
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def close(self):
        pass


class Replies(list):
    """Всё, что бот сделал в ответ на одно действие пользователя."""

    @property
    def text(self) -> str:
        """Тексты всех сообщений одной строкой — удобно проверять через `in`."""
        return "\n".join(getattr(m, "text", None) or getattr(m, "caption", None) or "" for m in self)

    def to(self, chat_id: int) -> "Replies":
        """Только то, что ушло в чат chat_id."""
        return Replies(m for m in self if getattr(m, "chat_id", None) == chat_id)

    def of(self, method: str) -> "Replies":
        """Только запросы одного вида: SendMessage, SendMediaGroup, SendDocument…"""
        return Replies(m for m in self if type(m).__name__ == method)

    @property
    def buttons(self) -> list[str]:
        result = []
        for m in self:
            markup = getattr(m, "reply_markup", None)
            rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []
            result += [button.text for row in rows for button in row]
        return result

    @property
    def alerts(self) -> list[str]:
        """Всплывающие подсказки в ответ на нажатие кнопки."""
        return [m.text for m in self if isinstance(m, AnswerCallbackQuery) and m.text]


class Chat:
    """Пользователь Telegram: пишет боту, шлёт файлы, жмёт кнопки. Каждый метод возвращает Replies."""

    def __init__(self, tg, user_id: int, first_name: str):
        self.tg = tg
        self.id = user_id
        self.user = {"id": user_id, "is_bot": False, "first_name": first_name}

    async def _feed(self, update: dict) -> Replies:
        self.tg.api.requests.clear()
        update = Update.model_validate({"update_id": next(_ids), **update}, context={"bot": self.tg.bot})
        await self.tg.dp.feed_update(self.tg.bot, update)
        return Replies(self.tg.api.requests)

    def _message(self, **fields) -> dict:
        return {"message_id": next(_ids), "date": int(time.time()),
                "chat": {"id": self.id, "type": "private"}, "from": self.user, **fields}

    async def send(self, text: str) -> Replies:
        fields = {"text": text}
        if text.startswith("/"):  # Telegram помечает команды — без этого бот их не распознает
            fields["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        return await self._feed({"message": self._message(**fields)})

    async def send_photo(self, key: str | None = None, album: str | None = None) -> Replies:
        """Фото: Telegram присылает несколько размеров, бот должен взять самый большой (photo_…)."""
        key = key or str(next(_ids))
        fields = {"photo": [
            {"file_id": f"small_{key}", "file_unique_id": f"s_{key}", "width": 90, "height": 90},
            {"file_id": f"photo_{key}", "file_unique_id": f"u_{key}", "width": 1280, "height": 960},
        ]}
        if album:
            fields["media_group_id"] = album
        return await self._feed({"message": self._message(**fields)})

    async def send_album(self, count: int) -> Replies:
        """Альбом приходит как count отдельных сообщений с общим media_group_id."""
        album = f"album_{next(_ids)}"
        replies = Replies()
        for _ in range(count):
            replies += await self.send_photo(album=album)
        return replies

    async def send_pdf(self, name: str = "скан.pdf", key: str | None = None) -> Replies:
        key = key or str(next(_ids))
        return await self._feed({"message": self._message(document={
            "file_id": f"doc_{key}", "file_unique_id": f"d_{key}", "file_name": name, "mime_type": "application/pdf",
        })})

    async def send_contact(self, phone: str, owner_id: int | None = None) -> Replies:
        """Контакт. owner_id — чей это номер (по умолчанию свой)."""
        return await self._feed({"message": self._message(contact={
            "phone_number": phone, "first_name": "Контакт", "user_id": owner_id if owner_id is not None else self.id,
        })})

    async def press(self, data: str | CallbackData, message_text: str = "Сообщение с кнопкой") -> Replies:
        if isinstance(data, CallbackData):
            data = data.pack()
        return await self._feed({"callback_query": {
            "id": str(next(_ids)), "from": self.user, "chat_instance": "test",
            "data": data, "message": self._message(text=message_text),
        }})

    # ---------- готовые шаги сценариев ----------

    async def register(self, full_name: str = "Иванов Иван Иванович", phone: str = "79991234567") -> Replies:
        await self.send("/start")
        await self.press("consent")
        await self.send(full_name)
        return await self.send_contact(phone)

    async def choose(self, doc_id: str) -> Replies:
        """Нажать документ в списке «Какой документ отправляете?»."""
        return await self.press(kb.DocCallback(action="upload", doc_id=doc_id))

    async def done(self) -> Replies:
        return await self.press("upload:done")

    async def submit(self, doc_id: str, photos: int = 1) -> Replies:
        """Выбрать документ, прислать фото и нажать «Готово»."""
        await self.choose(doc_id)
        for _ in range(photos):
            await self.send_photo()
        return await self.done()


class Lawyer(Chat):
    async def review(self, action: str, client_id: int, doc_id: str) -> Replies:
        """action: files / accept / reject / open."""
        return await self.press(kb.ReviewCallback(action=action, client_id=client_id, doc_id=doc_id))

    async def accept(self, client_id: int, doc_id: str) -> Replies:
        return await self.review("accept", client_id, doc_id)

    async def reject(self, client_id: int, doc_id: str, reason: str) -> Replies:
        await self.review("reject", client_id, doc_id)
        return await self.send(reason)

    async def open_card(self, client_id: int) -> Replies:
        return await self.press(kb.ClientCallback(action="open", client_id=client_id))


# ---------- фикстуры: то, что тест получает в параметрах ----------

@pytest.fixture(scope="session")
def tg():
    """Один бот и диспетчер на все тесты: роутер можно подключить к диспетчеру только один раз."""
    api = FakeTelegram()
    bot = Bot("123456:TEST", session=api, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(lawyer.router, client.router)

    async def run(coro) -> Replies:
        """Запустить что-то вне диалога (например, проверку напоминаний) и собрать, что бот отправил."""
        api.requests.clear()
        await coro
        return Replies(api.requests)

    return SimpleNamespace(api=api, bot=bot, dp=dp, run=run)


@pytest.fixture(autouse=True)
def clean_state(tg, tmp_path, monkeypatch):
    """Каждый тест начинается с пустой базы и пустой памяти бота — тесты не влияют друг на друга."""
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    monkeypatch.setattr(db, "_conn", conn)
    db.init_db()
    tg.dp.storage.storage.clear()  # состояния «выбрал документ», «пишу причину возврата»
    client._last_album.clear()
    tg.api.requests.clear()
    tg.api.blocked.clear()
    yield
    conn.close()


@pytest.fixture
def ivan(tg) -> Chat:
    return Chat(tg, 111, "Иван")


@pytest.fixture
def petr(tg) -> Chat:
    return Chat(tg, 222, "Пётр")


@pytest.fixture
def lawyer_chat(tg) -> Lawyer:
    return Lawyer(tg, LAWYER_ID, "Юрист")


@pytest.fixture
def daytime(monkeypatch):
    """Напоминания разрешены круглые сутки — чтобы тест не зависел от того, когда его запустили."""
    monkeypatch.setattr(reminders, "REMIND_FROM", 0)
    monkeypatch.setattr(reminders, "REMIND_TO", 24)


def set_client(user_id: int, **fields) -> None:
    """Подправить клиента в базе — например, «перемотать время» его последней активности."""
    with db._conn:
        for column, value in fields.items():
            db._conn.execute(f"UPDATE clients SET {column} = ? WHERE id = ?", (value, user_id))
