"""Отправка документов клиентом."""
import pytest

from bot import db, keyboards as kb, texts
from bot.checklist import CHECKLIST
from conftest import LAWYER_ID


@pytest.fixture
async def registered(ivan):
    await ivan.register()
    return ivan


async def test_document_list_shows_every_item(registered):
    replies = await registered.send(texts.BTN_SEND)
    assert texts.CHOOSE_DOC in replies.text
    assert len(replies.buttons) == len(CHECKLIST)


async def test_choosing_document_shows_hint(registered):
    replies = await registered.choose("passport")
    assert "Все развороты" in replies.text, "описание из checklist.json"
    assert "📎 → «Файл»" in replies.text, "подсказка, как отправить PDF"


async def test_album_gets_single_reply(registered):
    await registered.choose("passport")
    replies = await registered.send_album(5)
    assert len(replies.of("SendMessage")) == 1, "на альбом — один ответ, а не пять"
    assert db.count_files(registered.id, "passport") == 5


async def test_biggest_photo_size_is_saved(registered):
    await registered.choose("passport")
    await registered.send_photo(key="p1")
    assert db.get_files(registered.id, "passport")[0]["file_id"] == "photo_p1"


async def test_pdf_is_accepted(registered):
    await registered.choose("passport")
    replies = await registered.send_pdf("паспорт.pdf")
    assert texts.FILE_RECEIVED in replies.text
    saved = db.get_files(registered.id, "passport")[0]
    assert saved["kind"] == "document" and saved["file_name"] == "паспорт.pdf"


async def test_duplicate_file_is_reported(registered):
    await registered.choose("passport")
    await registered.send_photo(key="same")
    replies = await registered.send_photo(key="same")
    assert texts.FILE_DUPLICATE in replies.text
    assert db.count_files(registered.id, "passport") == 1


async def test_text_while_uploading_asks_for_file(registered):
    await registered.choose("passport")
    replies = await registered.send("а куда отправлять?")
    assert texts.EXPECT_FILE in replies.text


async def test_done_without_files_shows_alert(registered):
    await registered.choose("passport")
    replies = await registered.done()
    assert texts.NO_FILES_YET in replies.alerts
    assert db.get_status(registered.id, "passport") is None


async def test_done_sends_document_to_lawyer(registered):
    replies = await registered.submit("passport", photos=3)
    assert "отправлено на проверку (3 файла)" in replies.to(registered.id).text
    assert db.get_status(registered.id, "passport") == "review"

    note = replies.to(LAWYER_ID)
    assert "Иванов Иван Иванович" in note.text and "+79991234567" in note.text and "Файлов: 3" in note.text
    assert note.buttons == [texts.BTN_FILES, texts.BTN_ACCEPT, texts.BTN_REJECT]


async def test_only_optional_documents_can_be_marked_missing(registered):
    replies = await registered.choose("passport")
    assert texts.BTN_NOT_APPLICABLE not in replies.buttons, "паспорт обязателен"
    replies = await registered.choose("marriage")
    assert texts.BTN_NOT_APPLICABLE in replies.buttons


async def test_mark_document_missing(registered):
    await registered.choose("marriage")
    await registered.send_photo()  # прислал по ошибке, потом передумал
    replies = await registered.press("upload:na")
    assert "такого документа нет" in replies.text
    assert db.get_status(registered.id, "marriage") == "na"
    assert db.count_files(registered.id, "marriage") == 0, "случайно присланные файлы убираются"


async def test_accepted_documents_hidden_from_list(registered, lawyer_chat):
    await registered.submit("passport")
    await lawyer_chat.accept(registered.id, "passport")
    replies = await registered.send(texts.BTN_SEND)
    assert not any("Паспорт" in button for button in replies.buttons)
    assert len(replies.buttons) == len(CHECKLIST) - 1


async def test_file_without_choice_is_kept_and_assigned(registered):
    replies = await registered.send_photo()
    assert texts.UNSORTED_ASK in replies.text
    assert len(replies.buttons) == len(CHECKLIST)

    replies = await registered.press(kb.DocCallback(action="assign", doc_id="snils"))
    assert "Прикрепил к «СНИЛС»" in replies.text
    assert db.get_status(registered.id, "snils") == "review"
    assert replies.to(LAWYER_ID), "юрист получил уведомление"


async def test_unsorted_album_asks_once(registered):
    replies = await registered.send_album(4)
    assert len(replies.of("SendMessage")) == 1


async def test_assign_button_pressed_twice_is_harmless(registered):
    await registered.send_photo()
    await registered.press(kb.DocCallback(action="assign", doc_id="snils"))
    replies = await registered.press(kb.DocCallback(action="assign", doc_id="inn"))
    assert texts.NOTHING_TO_ASSIGN in replies.alerts
    assert db.get_status(registered.id, "inn") is None


async def test_files_not_lost_when_bot_restarts_mid_upload(tg, registered):
    """После перезапуска бот забыл выбранный документ — файл не теряется, а уходит в неразобранные."""
    await registered.choose("passport")
    tg.dp.storage.storage.clear()  # «перезапуск»
    replies = await registered.send_photo()
    assert texts.UNSORTED_ASK in replies.text


async def test_old_button_does_not_break_anything(registered):
    replies = await registered.done()  # «Готово» из давно закрытой отправки
    assert texts.STALE_BUTTON in replies.alerts


async def test_button_for_document_removed_from_checklist(registered):
    replies = await registered.press(kb.DocCallback(action="upload", doc_id="removed_doc"))
    assert texts.STALE_BUTTON in replies.alerts


async def test_status_command(registered):
    await registered.submit("passport")
    replies = await registered.send("/status")
    assert "🕓 Паспорт" in replies.text
    assert (await registered.send(texts.BTN_STATUS)).text == replies.text, "кнопка = команда"


async def test_random_text_shows_menu(registered):
    replies = await registered.send("спасибо!")
    assert texts.UNKNOWN in replies.text
    assert texts.BTN_SEND in replies.buttons
