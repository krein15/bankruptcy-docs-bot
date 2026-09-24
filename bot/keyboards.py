"""Все кнопки бота."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from bot.checklist import CHECKLIST


class DocCallback(CallbackData, prefix="doc"):
    """Кнопка с документом. action: upload — выбрать для отправки,
    resend — отправить заново после возврата, assign — прикрепить неразобранные файлы."""
    action: str
    doc_id: str


class ReviewCallback(CallbackData, prefix="rv"):
    """Кнопки юриста под документом. action: files / accept / reject."""
    action: str
    client_id: int
    doc_id: str


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
        row = statuses.get(item["id"])
        status = row["status"] if row else None
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
