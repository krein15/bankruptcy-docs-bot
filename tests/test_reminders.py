"""Напоминания. «Время» перематываем, записывая в базу давнюю дату последней активности."""
import pytest

from bot import db, keyboards as kb, reminders, texts
from bot.checklist import CHECKLIST
from conftest import LAWYER_ID, LONG_AGO, set_client

pytestmark = pytest.mark.usefixtures("daytime")  # во всех тестах файла — «день»


@pytest.fixture
async def ivan_forgot_done(ivan):
    """Иван прислал 2 фото паспорта и не нажал «Готово»."""
    await ivan.register()
    await ivan.choose("passport")
    await ivan.send_photo()
    await ivan.send_photo()
    return ivan


# ---------- «прислал, но не нажал Готово» ----------

async def test_not_reminded_too_early(tg, ivan_forgot_done):
    assert not await tg.run(reminders.check_reminders(tg.bot))


async def test_reminded_after_silence_once(tg, ivan_forgot_done):
    set_client(ivan_forgot_done.id, last_activity_at=LONG_AGO)
    replies = await tg.run(reminders.check_reminders(tg.bot))
    assert texts.UNSUBMITTED in replies.to(ivan_forgot_done.id).text
    assert "📤 Отправить юристу: Паспорт (2)" in replies.buttons

    assert not await tg.run(reminders.check_reminders(tg.bot)), "второй раз про то же не напоминаем"


async def test_no_reminders_at_night(tg, ivan_forgot_done, monkeypatch):
    monkeypatch.setattr(reminders, "REMIND_FROM", 10)
    monkeypatch.setattr(reminders, "REMIND_TO", 10)  # «день» пустой — всегда ночь
    set_client(ivan_forgot_done.id, last_activity_at=LONG_AGO)
    assert not await tg.run(reminders.check_reminders(tg.bot))


async def test_submit_button_from_reminder(tg, ivan_forgot_done):
    ivan = ivan_forgot_done
    replies = await ivan.press(kb.DocCallback(action="submit", doc_id="passport"))
    assert "отправлено на проверку (2 файла)" in replies.to(ivan.id).text
    assert replies.to(LAWYER_ID), "юрист получил уведомление"
    assert db.get_status(ivan.id, "passport") == "review"

    replies = await ivan.press(kb.DocCallback(action="submit", doc_id="passport"))
    assert texts.STALE_BUTTON in replies.alerts, "повторное нажатие ничего не отправляет"


async def test_unsorted_files_reminder_offers_document_choice(tg, ivan):
    await ivan.register()
    await ivan.send_photo()  # без выбора документа
    set_client(ivan.id, last_activity_at=LONG_AGO)
    # Только это напоминание: «давно молчит» при такой перемотке времени пришло бы следом отдельным сообщением
    replies = await tg.run(reminders.remind_unsubmitted(tg.bot))
    assert texts.UNSORTED_REMINDER in replies.text
    assert len(replies.buttons) == len(CHECKLIST)


# ---------- «давно молчит» ----------

@pytest.fixture
async def silent_ivan(ivan):
    await ivan.register()
    await ivan.submit("passport")
    set_client(ivan.id, last_activity_at=LONG_AGO)
    return ivan


async def test_silent_client_gets_list_of_missing(tg, silent_ivan):
    replies = await tg.run(reminders.check_reminders(tg.bot))
    text = replies.to(silent_ivan.id).text
    assert "Осталось" in text and "⬜ СНИЛС" in text
    assert "Паспорт" not in text, "паспорт уже на проверке"
    assert replies.buttons == [texts.BTN_SEND]


async def test_reminder_button_opens_document_list(silent_ivan):
    replies = await silent_ivan.press("send")
    assert texts.CHOOSE_DOC in replies.text


async def test_silent_reminder_not_repeated_within_48_hours(tg, silent_ivan):
    await tg.run(reminders.check_reminders(tg.bot))
    assert not await tg.run(reminders.check_reminders(tg.bot))
    set_client(silent_ivan.id, last_reminder_at=LONG_AGO)  # «прошло ещё 48 часов»
    assert await tg.run(reminders.check_reminders(tg.bot))
    assert db.get_client(silent_ivan.id)["reminders_sent"] == 2


async def test_reminders_stop_after_limit(tg, silent_ivan):
    set_client(silent_ivan.id, reminders_sent=reminders.REMIND_MAX)
    assert not await tg.run(reminders.check_reminders(tg.bot))


async def test_any_client_action_resets_counter(tg, silent_ivan):
    set_client(silent_ivan.id, reminders_sent=3)
    await silent_ivan.send(texts.BTN_STATUS)
    client = db.get_client(silent_ivan.id)
    assert client["reminders_sent"] == 0 and client["last_activity_at"] > LONG_AGO


async def test_complete_client_not_reminded(tg, ivan):
    await ivan.register()
    for item in CHECKLIST:
        db.set_status(ivan.id, item["id"], "accepted")
    set_client(ivan.id, last_activity_at=LONG_AGO)
    assert not await tg.run(reminders.check_reminders(tg.bot))


async def test_unfinished_registration_not_reminded(tg, ivan):
    await ivan.send("/start")
    set_client(ivan.id, last_activity_at=LONG_AGO)
    assert not await tg.run(reminders.check_reminders(tg.bot))


async def test_blocked_bot_does_not_retry_every_minute(tg, silent_ivan):
    tg.api.blocked.add(silent_ivan.id)
    await tg.run(reminders.check_reminders(tg.bot))
    assert db.get_client(silent_ivan.id)["last_reminder_at"] is not None, "попытку всё равно запомнили"


# ---------- «Напомнить» из карточки клиента ----------

async def test_lawyer_reminds_manually(silent_ivan, lawyer_chat):
    replies = await lawyer_chat.press(kb.ClientCallback(action="remind", client_id=silent_ivan.id))
    assert "Осталось" in replies.to(silent_ivan.id).text
    assert texts.REMINDER_SENT in replies.alerts


async def test_manual_reminder_to_blocked_client(tg, silent_ivan, lawyer_chat):
    tg.api.blocked.add(silent_ivan.id)
    replies = await lawyer_chat.press(kb.ClientCallback(action="remind", client_id=silent_ivan.id))
    assert texts.REMINDER_FAILED in replies.alerts


async def test_nothing_to_remind_when_complete(ivan, lawyer_chat):
    await ivan.register()
    for item in CHECKLIST:
        db.set_status(ivan.id, item["id"], "accepted")
    replies = await lawyer_chat.press(kb.ClientCallback(action="remind", client_id=ivan.id))
    assert texts.NOTHING_TO_REMIND in replies.alerts
    assert not replies.to(ivan.id)
