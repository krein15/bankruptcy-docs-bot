"""Сторона юриста: уведомления о новых документах, «Принять» / «Вернуть»."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputMediaDocument, InputMediaPhoto, Message

from bot import db, keyboards as kb, texts
from bot.checklist import BY_ID, is_complete
from bot.config import LAWYER_IDS

router = Router()
# Весь этот роутер — только для юристов. Остальные сообщения уходят дальше, в client.py
router.message.filter(F.from_user.id.in_(LAWYER_IDS))
router.callback_query.filter(F.from_user.id.in_(LAWYER_IDS))


class Review(StatesGroup):
    reason = State()  # юрист нажал «Вернуть» и пишет причину


async def notify_lawyers(bot: Bot, client, doc_id: str, count: int) -> None:
    """Сообщает всем юристам, что клиент прислал документ на проверку."""
    text = texts.NEW_SUBMISSION.format(
        name=escape(client["full_name"]),
        phone=escape(client["phone"]),
        title=escape(BY_ID[doc_id]["title"]),
        count=count,
    )
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


@router.callback_query(kb.ReviewCallback.filter(F.action == "files"))
async def show_files(callback: CallbackQuery, callback_data: kb.ReviewCallback, bot: Bot):
    files = db.get_files(callback_data.client_id, callback_data.doc_id)
    if not files:
        await callback.answer(texts.FILES_GONE, show_alert=True)
        return
    await callback.answer()
    client = db.get_client(callback_data.client_id)
    await callback.message.answer(texts.FILES_HEADER.format(
        title=escape(BY_ID[callback_data.doc_id]["title"]),
        name=escape(client["full_name"]),
    ))
    await send_files(bot, callback.message.chat.id, files)


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


@router.message(Review.reason, F.text)
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
