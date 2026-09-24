"""Сторона юриста: проверка документов, клиенты, карточка."""
import pytest

from bot import db, keyboards as kb, texts
from bot.checklist import CHECKLIST
from bot.handlers import lawyer
from conftest import LAWYER_ID


@pytest.fixture
async def ivan_sent_passport(ivan):
    await ivan.register()
    await ivan.choose("passport")
    await ivan.send_album(2)
    await ivan.send_pdf()
    await ivan.done()
    return ivan


async def test_client_cannot_press_lawyer_buttons(ivan_sent_passport):
    ivan = ivan_sent_passport
    replies = await ivan.press(kb.ReviewCallback(action="accept", client_id=ivan.id, doc_id="passport"))
    assert texts.STALE_BUTTON in replies.alerts
    assert db.get_status(ivan.id, "passport") == "review"


async def test_files_forwarded_to_lawyer(ivan_sent_passport, lawyer_chat):
    replies = await lawyer_chat.review("files", ivan_sent_passport.id, "passport")
    assert "Паспорт — Иванов Иван Иванович" in replies.text
    assert len(replies.of("SendMediaGroup")) == 1, "два фото — одним альбомом"
    assert len(replies.of("SendDocument")) == 1, "PDF отдельно: Telegram не смешивает их с фото"


async def test_accept(ivan_sent_passport, lawyer_chat):
    ivan = ivan_sent_passport
    replies = await lawyer_chat.accept(ivan.id, "passport")
    assert db.get_status(ivan.id, "passport") == "accepted"
    assert "Принято" in replies.to(LAWYER_ID).text, "уведомление юриста помечено"
    assert "Юрист принял документ: <b>Паспорт</b>" in replies.to(ivan.id).text


async def test_second_accept_is_blocked(ivan_sent_passport, lawyer_chat):
    await lawyer_chat.accept(ivan_sent_passport.id, "passport")
    replies = await lawyer_chat.accept(ivan_sent_passport.id, "passport")
    assert texts.ALREADY_PROCESSED in replies.alerts
    assert not replies.to(ivan_sent_passport.id), "клиенту второй раз не пишем"


async def test_reject_with_reason(ivan_sent_passport, lawyer_chat):
    ivan = ivan_sent_passport
    replies = await lawyer_chat.reject(ivan.id, "passport", "Нет разворота с <пропиской>")
    assert db.get_status(ivan.id, "passport") == "rejected"
    assert db.count_files(ivan.id, "passport") == 0, "старые файлы больше не показываются"

    to_ivan = replies.to(ivan.id)
    assert "Нет разворота с &lt;пропиской&gt;" in to_ivan.text
    assert to_ivan.buttons == [texts.BTN_RESEND]
    assert "Возвращено" in replies.of("EditMessageText").text, "уведомление юриста помечено"


async def test_resend_after_rejection(ivan_sent_passport, lawyer_chat):
    ivan = ivan_sent_passport
    await lawyer_chat.reject(ivan.id, "passport", "Размыто")
    replies = await ivan.press(kb.DocCallback(action="resend", doc_id="passport"))
    assert "Все развороты" in replies.text
    await ivan.send_photo()
    replies = await ivan.done()
    assert "Файлов: 1" in replies.to(LAWYER_ID).text, "юрист видит только новые файлы"
    assert db.get_status(ivan.id, "passport") == "review"


async def test_cancel_rejection(ivan_sent_passport, lawyer_chat):
    await lawyer_chat.review("reject", ivan_sent_passport.id, "passport")
    replies = await lawyer_chat.send("/cancel")
    assert texts.REJECT_CANCELLED in replies.text
    assert db.get_status(ivan_sent_passport.id, "passport") == "review"


async def test_command_is_not_taken_as_rejection_reason(ivan_sent_passport, lawyer_chat):
    await lawyer_chat.review("reject", ivan_sent_passport.id, "passport")
    await lawyer_chat.send("/clients")
    assert db.get_status(ivan_sent_passport.id, "passport") == "review"
    await lawyer_chat.send("Размыто")
    assert db.get_status(ivan_sent_passport.id, "passport") == "rejected"


async def test_everything_collected(ivan, lawyer_chat):
    await ivan.register()
    for item in CHECKLIST[1:]:  # всё, кроме паспорта, уже закрыто
        db.set_status(ivan.id, item["id"], "accepted")
    await ivan.submit("passport")
    replies = await lawyer_chat.accept(ivan.id, "passport")
    assert texts.ALL_DONE in replies.to(ivan.id).text
    assert "Иванов Иван Иванович: все документы собраны" in replies.to(LAWYER_ID).text


async def test_lawyer_can_also_be_client(lawyer_chat):
    """Юрист может пройти путь клиента сам — так бот и показывают на демо."""
    await lawyer_chat.register(full_name="Юристов Юрий Юрьевич")
    replies = await lawyer_chat.submit("passport")
    assert "Новые документы на проверку" in replies.to(LAWYER_ID).text


# ---------- список клиентов и карточка ----------

async def test_no_clients_yet(lawyer_chat):
    replies = await lawyer_chat.send("/clients")
    assert texts.NO_CLIENTS in replies.text


async def test_clients_waiting_for_review_come_first(ivan, petr, lawyer_chat):
    await petr.register(full_name="Петров Пётр Петрович")
    await petr.submit("passport")
    await ivan.register()  # Иван активен позже, но проверять у него нечего
    replies = await lawyer_chat.send("/clients")
    assert replies.buttons[0].startswith("Петров Пётр Петрович — 0/") and "🕓1" in replies.buttons[0]
    assert replies.buttons[1].startswith("Иванов Иван Иванович")
    assert replies.buttons[-1] == texts.BTN_EXPORT


async def test_long_client_list_is_truncated(ivan, petr, tg, lawyer_chat, monkeypatch):
    monkeypatch.setattr(lawyer, "CLIENTS_LIMIT", 1)
    await ivan.register()
    await petr.register(full_name="Петров Пётр Петрович")
    replies = await lawyer_chat.send("/clients")
    assert "Показаны первые 1" in replies.text
    assert len(replies.buttons) == 2  # один клиент + «Выгрузить в Excel»


async def test_client_card(ivan_sent_passport, lawyer_chat):
    replies = await lawyer_chat.open_card(ivan_sent_passport.id)
    assert "Иванов Иван Иванович" in replies.text and "+79991234567" in replies.text
    assert "(при наличии)" not in replies.text and "нужно прислать" not in replies.text, "карточка — компактная"
    assert "🕓 Паспорт (3)" in replies.buttons
    assert texts.BTN_REMIND in replies.buttons and texts.BTN_ALL_CLIENTS in replies.buttons


async def test_open_document_from_card_offers_review(ivan_sent_passport, lawyer_chat):
    replies = await lawyer_chat.review("open", ivan_sent_passport.id, "passport")
    assert replies.of("SendMediaGroup"), "файлы пришли"
    assert texts.BTN_ACCEPT in replies.buttons, "и сразу кнопки «Принять» / «Вернуть»"


async def test_open_accepted_document_without_review_buttons(ivan_sent_passport, lawyer_chat):
    await lawyer_chat.accept(ivan_sent_passport.id, "passport")
    replies = await lawyer_chat.review("open", ivan_sent_passport.id, "passport")
    assert texts.BTN_ACCEPT not in replies.buttons


async def test_back_to_clients(ivan_sent_passport, lawyer_chat):
    replies = await lawyer_chat.press("clients")
    assert "Клиенты: 1" in replies.text


async def test_client_cannot_use_lawyer_commands(ivan):
    await ivan.register()
    for command in ("/clients", "/export"):
        replies = await ivan.send(command)
        assert texts.UNKNOWN in replies.text, command
