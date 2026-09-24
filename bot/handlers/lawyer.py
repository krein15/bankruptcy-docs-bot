"""Сторона юриста: проверка документов, список клиентов, карточка клиента, выгрузка в Excel."""
import logging
from datetime import datetime
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InputMediaDocument, InputMediaPhoto, Message,
)

from bot import db, export, keyboards as kb, reminders, texts
from bot.checklist import BY_ID, in_review, is_complete
from bot.config import LAWYER_IDS, TIMEZONE

CLIENTS_LIMIT = 50  # больше кнопок в одном сообщении неудобно листать; остальные — в Excel

router = Router()
# Весь этот роутер — только для юристов. Остальные сообщения уходят дальше, в client.py
router.message.filter(F.from_user.id.in_(LAWYER_IDS))
router.callback_query.filter(F.from_user.id.in_(LAWYER_IDS))


class Review(StatesGroup):
    reason = State()  # юрист нажал «Вернуть» и пишет причину


def _review_text(client, doc_id: str, count: int) -> str:
    return texts.NEW_SUBMISSION.format(
        name=escape(client["full_name"]),
        phone=escape(client["phone"]),
        title=escape(BY_ID[doc_id]["title"]),
        count=count,
    )


async def notify_lawyers(bot: Bot, client, doc_id: str, count: int) -> None:
    """Сообщает всем юристам, что клиент прислал документ на проверку."""
    text = _review_text(client, doc_id, count)
    for lawyer_id in LAWYER_IDS:
        try:
            await bot.send_message(lawyer_id, text, reply_markup=kb.review(client["id"], doc_id))
        except TelegramAPIError as e:  # например, юрист ни разу не открывал бота
            logging.warning("Не удалось уведомить юриста %s: %s", lawyer_id, e)


async def notify_client(bot: Bot, client_id: int, text: str,
                        reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await bot.send_message(client_id, text, reply_markup=reply_markup)
    except TelegramAPIError as e:  # например, клиент заблокировал бота
        logging.warning("Не удалось написать клиенту %s: %s", client_id, e)


async def send_files(bot: Bot, chat_id: int, files: list) -> None:
    """Пересылает файлы по file_id. Фото и документы Telegram не смешивает в одном альбоме,
    а в альбоме бывает от 2 до 10 штук — отсюда такая нарезка."""
    photos = [InputMediaPhoto(media=f["file_id"]) for f in files if f["kind"] == "photo"]
    documents = [InputMediaDocument(media=f["file_id"]) for f in files if f["kind"] == "document"]
    for group in (photos, documents):
        for i in range(0, len(group), 10):
            chunk = group[i:i + 10]
            if len(chunk) > 1:
                await bot.send_media_group(chat_id, chunk)
            elif isinstance(chunk[0], InputMediaPhoto):
                await bot.send_photo(chat_id, chunk[0].media)
            else:
                await bot.send_document(chat_id, chunk[0].media)


async def _still_in_review(callback: CallbackQuery, client_id: int, doc_id: str) -> bool:
    """Защита от двойного нажатия и от второго юриста, который уже всё решил."""
    if db.get_status(client_id, doc_id) == "review":
        return True
    await callback.answer(texts.ALREADY_PROCESSED, show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)
    return False


@router.callback_query(kb.ReviewCallback.filter(F.action.in_({"files", "open"})))
async def show_files(callback: CallbackQuery, callback_data: kb.ReviewCallback, bot: Bot):
    client_id, doc_id = callback_data.client_id, callback_data.doc_id
    files = db.get_files(client_id, doc_id)
    if not files or doc_id not in BY_ID:
        await callback.answer(texts.FILES_GONE, show_alert=True)
        return
    await callback.answer()
    client = db.get_client(client_id)
    await callback.message.answer(texts.FILES_HEADER.format(
        title=escape(BY_ID[doc_id]["title"]),
        name=escape(client["full_name"]),
    ))
    await send_files(bot, callback.message.chat.id, files)
    # Из карточки клиента: если документ ждёт проверки — сразу даём кнопки «Принять» / «Вернуть»
    if callback_data.action == "open" and db.get_status(client_id, doc_id) == "review":
        await callback.message.answer(_review_text(client, doc_id, len(files)), reply_markup=kb.review(client_id, doc_id))


@router.callback_query(kb.ReviewCallback.filter(F.action == "accept"))
async def accept(callback: CallbackQuery, callback_data: kb.ReviewCallback, bot: Bot):
    client_id, doc_id = callback_data.client_id, callback_data.doc_id
    if not await _still_in_review(callback, client_id, doc_id):
        return

    db.set_status(client_id, doc_id, "accepted")
    # edit_text без reply_markup заодно убирает кнопки
    await callback.message.edit_text(callback.message.html_text + texts.MARK_ACCEPTED)
    await callback.answer()

    title = escape(BY_ID[doc_id]["title"])
    await notify_client(bot, client_id, texts.DOC_ACCEPTED.format(title=title))
    if is_complete(db.get_statuses(client_id)):
        await notify_client(bot, client_id, texts.ALL_DONE)
        client = db.get_client(client_id)
        await callback.message.answer(texts.CLIENT_COMPLETE.format(name=escape(client["full_name"])))


@router.callback_query(kb.ReviewCallback.filter(F.action == "reject"))
async def ask_reject_reason(callback: CallbackQuery, callback_data: kb.ReviewCallback, state: FSMContext):
    client_id, doc_id = callback_data.client_id, callback_data.doc_id
    if not await _still_in_review(callback, client_id, doc_id):
        return

    await state.set_state(Review.reason)
    # Запоминаем, какое уведомление потом пометить «Возвращено»
    await state.update_data(
        client_id=client_id,
        doc_id=doc_id,
        message_id=callback.message.message_id,
        message_html=callback.message.html_text,
    )
    await callback.message.answer(texts.ASK_REJECT_REASON.format(title=escape(BY_ID[doc_id]["title"])))
    await callback.answer()


@router.message(Review.reason, Command("cancel"))
async def cancel_reject(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(texts.REJECT_CANCELLED)


@router.message(Review.reason, F.text, ~F.text.startswith("/"))  # команды — не причина возврата
async def reject_with_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    client_id, doc_id = data["client_id"], data["doc_id"]
    if db.get_status(client_id, doc_id) != "review":
        await message.answer(texts.ALREADY_PROCESSED)
        return

    comment = message.text
    db.set_status(client_id, doc_id, "rejected", comment)
    db.archive_files(client_id, doc_id)  # старые файлы не нужны — клиент пришлёт новые

    await bot.edit_message_text(
        data["message_html"] + texts.MARK_REJECTED.format(comment=escape(comment)),
        chat_id=message.chat.id,
        message_id=data["message_id"],
    )
    await message.answer(texts.REJECT_SENT)
    await notify_client(
        bot, client_id,
        texts.DOC_REJECTED.format(title=escape(BY_ID[doc_id]["title"]), comment=escape(comment)),
        reply_markup=kb.resend(doc_id),
    )


# ---------- клиенты ----------

async def _send_clients(message: Message) -> None:
    clients = db.get_clients()
    if not clients:
        await message.answer(texts.NO_CLIENTS)
        return
    all_statuses = db.get_all_statuses()
    rows = [(client, all_statuses.get(client["id"], {})) for client in clients]
    # Сверху те, у кого есть что проверить; внутри — по свежести (sort сохраняет порядок из базы)
    rows.sort(key=lambda row: in_review(row[1]) == 0)

    text = texts.CLIENTS_HEADER.format(count=len(rows))
    if len(rows) > CLIENTS_LIMIT:
        text += texts.CLIENTS_TRUNCATED.format(shown=CLIENTS_LIMIT)
    await message.answer(text, reply_markup=kb.clients(rows[:CLIENTS_LIMIT]))


@router.message(Command("clients"))
async def clients_command(message: Message):
    await _send_clients(message)


@router.callback_query(F.data == "clients")
async def clients_button(callback: CallbackQuery):
    await callback.answer()
    await _send_clients(callback.message)


@router.callback_query(kb.ClientCallback.filter(F.action == "open"))
async def client_card(callback: CallbackQuery, callback_data: kb.ClientCallback):
    client = db.get_client(callback_data.client_id)
    if client is None:
        await callback.answer(texts.STALE_BUTTON)
        return
    statuses = db.get_statuses(client["id"])
    file_counts = db.count_files_by_doc(client["id"])
    await callback.answer()
    await callback.message.answer(
        texts.client_card(client, statuses, has_files=bool(file_counts)),
        reply_markup=kb.client_card(client["id"], statuses, file_counts),
    )


@router.callback_query(kb.ClientCallback.filter(F.action == "remind"))
async def remind_client(callback: CallbackQuery, callback_data: kb.ClientCallback, bot: Bot):
    client = db.get_client(callback_data.client_id)
    if client is None:
        await callback.answer(texts.STALE_BUTTON)
        return
    if is_complete(db.get_statuses(client["id"])):
        await callback.answer(texts.NOTHING_TO_REMIND, show_alert=True)
        return
    sent = await reminders.send_reminder(bot, client)
    await callback.answer(texts.REMINDER_SENT if sent else texts.REMINDER_FAILED, show_alert=not sent)


# ---------- выгрузка в Excel ----------

async def _send_export(message: Message) -> None:
    clients = db.get_clients()
    if not clients:
        await message.answer(texts.NO_CLIENTS)
        return
    date = datetime.now(TIMEZONE).strftime("%d.%m.%Y")
    report = export.build_report(clients, db.get_all_statuses())
    await message.answer_document(
        BufferedInputFile(report, filename=texts.EXPORT_FILENAME.format(date=date)),
        caption=texts.EXPORT_CAPTION.format(date=date),
    )


@router.message(Command("export"))
async def export_command(message: Message):
    await _send_export(message)


@router.callback_query(F.data == "export")
async def export_button(callback: CallbackQuery):
    await callback.answer()
    await _send_export(callback.message)
