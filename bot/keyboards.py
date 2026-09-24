"""Все кнопки бота."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from bot.checklist import BY_ID, CHECKLIST, status_of


class DocCallback(CallbackData, prefix="doc"):
    """Кнопка с документом. action: upload — выбрать для отправки,
    resend — отправить заново после возврата, assign — прикрепить неразобранные файлы,
    submit — отправить юристу то, что уже прислано (из напоминания)."""
    action: str
    doc_id: str


class ReviewCallback(CallbackData, prefix="rv"):
    """Кнопки юриста под документом. action: files / accept / reject / open (из карточки клиента)."""
    action: str
    client_id: int
    doc_id: str


class ClientCallback(CallbackData, prefix="cl"):
    """Кнопки юриста про клиента. action: open — карточка, remind — напомнить."""
    action: str
    client_id: int


def consent() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_CONSENT, callback_data="consent")
    return builder.as_markup()


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_SEND)],
            [KeyboardButton(text=texts.BTN_STATUS), KeyboardButton(text=texts.BTN_RULES)],
        ],
        resize_keyboard=True,
    )


def documents(statuses: dict, action: str) -> InlineKeyboardMarkup:
    """Документы списком кнопок. При обычной отправке уже принятые не показываем."""
    builder = InlineKeyboardBuilder()
    for item in CHECKLIST:
        status = status_of(statuses, item["id"])
        if action == "upload" and status == "accepted":
            continue
        builder.button(
            text=f"{texts.ICONS[status]} {item['title']}",
            callback_data=DocCallback(action=action, doc_id=item["id"]),
        )
    builder.adjust(1)  # по одной кнопке в ряд — названия длинные
    return builder.as_markup()


def upload(item: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_DONE, callback_data="upload:done")
    if not item["required"]:
        builder.button(text=texts.BTN_NOT_APPLICABLE, callback_data="upload:na")
    builder.adjust(1)
    return builder.as_markup()


def resend(doc_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_RESEND, callback_data=DocCallback(action="resend", doc_id=doc_id))
    return builder.as_markup()


def review(client_id: int, doc_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for action, text in (("files", texts.BTN_FILES), ("accept", texts.BTN_ACCEPT), ("reject", texts.BTN_REJECT)):
        builder.button(text=text, callback_data=ReviewCallback(action=action, client_id=client_id, doc_id=doc_id))
    builder.adjust(1, 2)  # «Файлы» сверху, «Принять» и «Вернуть» рядом
    return builder.as_markup()


# ---------- напоминания ----------

def send_documents() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.BTN_SEND, callback_data="send")
    return builder.as_markup()


def unsubmitted(docs: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    """Кнопки «Отправить юристу» для документов, по которым клиент не нажал «Готово»."""
    builder = InlineKeyboardBuilder()
    for doc_id, count in docs:
        builder.button(
            text=texts.BTN_SUBMIT.format(title=BY_ID[doc_id]["title"], count=count),
            callback_data=DocCallback(action="submit", doc_id=doc_id),
        )
    builder.adjust(1)
    return builder.as_markup()


# ---------- юрист: клиенты ----------

def clients(rows: list[tuple]) -> InlineKeyboardMarkup:
    """rows — пары (клиент, его статусы)."""
    builder = InlineKeyboardBuilder()
    for client, statuses in rows:
        builder.button(
            text=texts.client_label(client, statuses),
            callback_data=ClientCallback(action="open", client_id=client["id"]),
        )
    builder.button(text=texts.BTN_EXPORT, callback_data="export")
    builder.adjust(1)
    return builder.as_markup()


def client_card(client_id: int, statuses: dict, file_counts: dict[str, int]) -> InlineKeyboardMarkup:
    """Документы клиента, по которым есть файлы, плюс «Напомнить» и «Все клиенты»."""
    builder = InlineKeyboardBuilder()
    for item in CHECKLIST:
        count = file_counts.get(item["id"])
        if count:
            builder.button(
                text=f"{texts.ICONS[status_of(statuses, item['id'])]} {item['title']} ({count})",
                callback_data=ReviewCallback(action="open", client_id=client_id, doc_id=item["id"]),
            )
    builder.button(text=texts.BTN_REMIND, callback_data=ClientCallback(action="remind", client_id=client_id))
    builder.button(text=texts.BTN_ALL_CLIENTS, callback_data="clients")
    builder.adjust(1)
    return builder.as_markup()
