"""Сторона клиента: регистрация, приём файлов, статус."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot import config, db, keyboards as kb, texts
from bot.checklist import BY_ID
from bot.handlers.lawyer import notify_demo_visitor, notify_lawyers

router = Router()


@router.message.outer_middleware()
@router.callback_query.outer_middleware()
async def track_activity(handler, event: Message | CallbackQuery, data: dict):
    """Middleware — прослойка перед обработчиками: срабатывает на каждое сообщение и кнопку клиента.
    Любое действие клиента — это активность, от неё отсчитываются напоминания."""
    db.touch(event.from_user.id)
    return await handler(event, data)


async def send_to_review(bot: Bot, client, doc_id: str, count: int) -> None:
    """Документ уходит юристу: статус «на проверке» + уведомление."""
    db.set_status(client["id"], doc_id, "review")
    await notify_lawyers(bot, client, doc_id, count)


class Upload(StatesGroup):
    files = State()  # клиент выбрал документ и присылает файлы; в данных — doc_id


# ---------- этапы регистрации ----------
# Этап вычисляется по базе, а не хранится в памяти бота:
# после перезапуска клиент продолжит с того же места.

def client_stage(client) -> str:
    if client is None:
        return "new"
    if client["consent_at"] is None:
        return "consent"
    if client["full_name"] is None:
        return "name"
    if client["phone"] is None:
        return "phone"
    return "ready"


class Stage(Filter):
    """Пропускает сообщение, только если клиент на нужном этапе,
    и передаёт обработчику строку клиента из базы в параметре client."""

    def __init__(self, stage: str):
        self.stage = stage

    async def __call__(self, event: Message | CallbackQuery) -> bool | dict:
        client = db.get_client(event.from_user.id)
        if client_stage(client) != self.stage:
            return False
        return {"client": client}


async def ask_next_step(message: Message, client) -> None:
    """Показывает клиенту то, что ему нужно сделать сейчас."""
    stage = client_stage(client)
    if stage == "new":
        await message.answer(texts.NEED_START)
    elif stage == "consent":
        intro = texts.DEMO_INTRO if config.DEMO_MODE else ""
        await message.answer(intro + texts.START, reply_markup=kb.consent())
    elif stage == "name":
        await message.answer(texts.ASK_NAME)
    elif stage == "phone":
        await message.answer(texts.ASK_PHONE, reply_markup=kb.share_phone())
    else:
        await message.answer(texts.UNKNOWN, reply_markup=kb.main_menu())


async def finish_registration(message: Message) -> None:
    await message.answer(texts.REGISTERED + texts.status_text({}), reply_markup=kb.main_menu())
    await message.answer(texts.PHOTO_RULES)
    if config.DEMO_MODE:
        await message.answer(texts.DEMO_HINT)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    is_new = db.create_client(message.from_user.id)
    if is_new and config.DEMO_MODE:
        await notify_demo_visitor(bot, message.from_user)
    client = db.get_client(message.from_user.id)
    if client_stage(client) == "ready":
        statuses = db.get_statuses(client["id"])
        await message.answer(texts.WELCOME_BACK + texts.status_text(statuses), reply_markup=kb.main_menu())
    else:
        await ask_next_step(message, client)


@router.callback_query(Stage("consent"), F.data == "consent")
async def on_consent(callback: CallbackQuery):
    db.set_consent(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await ask_next_step(callback.message, db.get_client(callback.from_user.id))


@router.message(Stage("name"), F.text, ~F.text.startswith("/"))
async def on_name(message: Message):
    full_name = " ".join(message.text.split())
    parts = full_name.split(" ")
    if len(parts) < 2 or len(full_name) > 100 or not all(p.replace("-", "").isalpha() for p in parts):
        await message.answer(texts.NAME_INVALID)
        return
    db.set_name(message.from_user.id, full_name)
    if config.DEMO_MODE:
        # В демо телефон не спрашиваем: посетитель не обязан давать номер, чтобы посмотреть бота
        db.set_phone(message.from_user.id, texts.DEMO_PHONE)
        await finish_registration(message)
        return
    await ask_next_step(message, db.get_client(message.from_user.id))


@router.message(Stage("phone"), F.contact)
async def on_phone(message: Message):
    # Кнопка «Поделиться номером» присылает контакт самого пользователя.
    # Если прислали чужой контакт из записной книжки — не принимаем.
    if message.contact.user_id != message.from_user.id:
        await message.answer(texts.PHONE_NOT_OWN)
        return
    phone = message.contact.phone_number
    db.set_phone(message.from_user.id, phone if phone.startswith("+") else "+" + phone)
    await finish_registration(message)


def demo_only(_) -> bool:
    return config.DEMO_MODE


@router.message(Command("reset"), demo_only)
async def demo_reset(message: Message, state: FSMContext):
    """Демо: удалить свои данные и пройти всё заново."""
    await state.clear()
    db.delete_client(message.from_user.id)
    await message.answer(texts.DEMO_RESET_DONE, reply_markup=ReplyKeyboardRemove())


# ---------- меню ----------

@router.message(Stage("ready"), Command("status"))
@router.message(Stage("ready"), F.text == texts.BTN_STATUS)
async def show_status(message: Message, client):
    await message.answer(texts.status_text(db.get_statuses(client["id"])))


@router.message(F.text == texts.BTN_RULES)
async def show_rules(message: Message):
    await message.answer(texts.PHOTO_RULES)


async def show_documents(message: Message, client, state: FSMContext) -> None:
    await state.clear()
    markup = kb.documents(db.get_statuses(client["id"]), action="upload")
    if not markup.inline_keyboard:
        await message.answer(texts.NOTHING_TO_SEND)
        return
    await message.answer(texts.CHOOSE_DOC, reply_markup=markup)


@router.message(Stage("ready"), F.text == texts.BTN_SEND)
async def choose_document(message: Message, client, state: FSMContext):
    await show_documents(message, client, state)


@router.callback_query(Stage("ready"), F.data == "send")  # кнопка из напоминания
async def choose_document_from_reminder(callback: CallbackQuery, client, state: FSMContext):
    await callback.answer()
    await show_documents(callback.message, client, state)


# ---------- приём файлов ----------

def file_info(message: Message) -> tuple[str, str, str, str | None]:
    """file_id, file_unique_id, вид и имя файла из сообщения с фото или документом."""
    if message.photo:
        photo = message.photo[-1]  # Telegram присылает несколько размеров, берём самый большой
        return photo.file_id, photo.file_unique_id, "photo", None
    doc = message.document
    return doc.file_id, doc.file_unique_id, "document", doc.file_name


_last_album: dict[int, str] = {}  # user_id → media_group_id последнего альбома


def is_first_in_album(message: Message) -> bool:
    """Альбом из 10 фото приходит как 10 отдельных сообщений.
    Отвечаем только на первое, чтобы не засыпать клиента одинаковыми ответами."""
    album = message.media_group_id
    if album is None:
        return True
    if _last_album.get(message.from_user.id) == album:
        return False
    _last_album[message.from_user.id] = album
    return True


@router.callback_query(Stage("ready"), kb.DocCallback.filter(F.action.in_({"upload", "resend"})))
async def start_upload(callback: CallbackQuery, callback_data: kb.DocCallback, state: FSMContext):
    item = BY_ID.get(callback_data.doc_id)
    if item is None:  # документ убрали из checklist.json, а кнопка осталась
        await callback.answer(texts.STALE_BUTTON)
        return
    await state.set_state(Upload.files)
    await state.update_data(doc_id=item["id"])
    if callback_data.action == "upload":
        # список документов заменяем подсказкой
        await callback.message.edit_text(texts.upload_prompt(item), reply_markup=kb.upload(item))
    else:
        # сообщение о возврате оставляем — в нём комментарий юриста
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(texts.upload_prompt(item), reply_markup=kb.upload(item))
    await callback.answer()


@router.message(Stage("ready"), Upload.files, F.photo | F.document)
async def receive_file(message: Message, client, state: FSMContext):
    doc_id = (await state.get_data())["doc_id"]
    info = file_info(message)
    saved = db.add_file(client["id"], doc_id, *info)
    logging.info("Файл от клиента %s: %s %s → %s%s", client["id"], info[2], info[3] or "", doc_id,
                 "" if saved else " (дубль)")
    if not is_first_in_album(message):
        return
    if saved or message.media_group_id:
        await message.answer(texts.FILE_RECEIVED, reply_markup=kb.upload(BY_ID[doc_id]))
    else:
        await message.answer(texts.FILE_DUPLICATE)


@router.callback_query(Stage("ready"), Upload.files, F.data == "upload:done")
async def finish_upload(callback: CallbackQuery, client, state: FSMContext, bot: Bot):
    doc_id = (await state.get_data())["doc_id"]
    count = db.count_files(client["id"], doc_id)
    if count == 0:
        await callback.answer(texts.NO_FILES_YET, show_alert=True)
        return

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer(
        texts.SUBMITTED.format(title=escape(BY_ID[doc_id]["title"]), count=texts.files_count(count))
    )
    await send_to_review(bot, client, doc_id, count)


@router.callback_query(Stage("ready"), kb.DocCallback.filter(F.action == "submit"))
async def submit_from_reminder(callback: CallbackQuery, callback_data: kb.DocCallback, client,
                               state: FSMContext, bot: Bot):
    """Кнопка «Отправить юристу» из напоминания — то же, что «Готово»."""
    doc_id = callback_data.doc_id
    count = db.count_files(client["id"], doc_id)
    if doc_id not in BY_ID or count == 0 or db.get_status(client["id"], doc_id) in ("review", "accepted"):
        await callback.answer(texts.STALE_BUTTON)
        return
    if (await state.get_data()).get("doc_id") == doc_id:
        await state.clear()  # клиент ещё «в загрузке» этого документа — она закончена
    await callback.answer()
    await callback.message.answer(
        texts.SUBMITTED.format(title=escape(BY_ID[doc_id]["title"]), count=texts.files_count(count))
    )
    await send_to_review(bot, client, doc_id, count)


@router.callback_query(Stage("ready"), Upload.files, F.data == "upload:na")
async def mark_not_applicable(callback: CallbackQuery, client, state: FSMContext):
    doc_id = (await state.get_data())["doc_id"]
    await state.clear()
    db.archive_files(client["id"], doc_id)
    db.set_status(client["id"], doc_id, "na")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await callback.message.answer(texts.MARKED_NA.format(title=escape(BY_ID[doc_id]["title"])))


@router.message(Stage("ready"), F.photo | F.document)
async def receive_unsorted(message: Message, client):
    """Файл прислали, не выбрав документ. Сохраняем без пункта и спрашиваем, что это."""
    info = file_info(message)
    db.add_file(client["id"], None, *info)
    logging.info("Файл от клиента %s без выбора документа: %s %s", client["id"], info[2], info[3] or "")
    if is_first_in_album(message):
        markup = kb.documents(db.get_statuses(client["id"]), action="assign")
        await message.answer(texts.UNSORTED_ASK, reply_markup=markup)


@router.callback_query(Stage("ready"), kb.DocCallback.filter(F.action == "assign"))
async def assign_unsorted(callback: CallbackQuery, callback_data: kb.DocCallback, client, bot: Bot):
    item = BY_ID.get(callback_data.doc_id)
    if item is None:
        await callback.answer(texts.STALE_BUTTON)
        return
    if db.assign_unsorted(client["id"], item["id"]) == 0:
        await callback.answer(texts.NOTHING_TO_ASSIGN)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    count = db.count_files(client["id"], item["id"])
    await callback.message.edit_text(texts.ASSIGNED.format(title=escape(item["title"]), count=texts.files_count(count)))
    await callback.answer()
    await send_to_review(bot, client, item["id"], count)


# ---------- всё остальное ----------

@router.message()
async def fallback(message: Message, state: FSMContext):
    if await state.get_state() == Upload.files:
        await message.answer(texts.EXPECT_FILE)
        return
    await ask_next_step(message, db.get_client(message.from_user.id))


@router.callback_query()
async def stale_button(callback: CallbackQuery):
    await callback.answer(texts.STALE_BUTTON)
