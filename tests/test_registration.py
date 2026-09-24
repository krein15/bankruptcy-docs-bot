"""Регистрация клиента: согласие → ФИО → телефон."""
from bot import db, texts


async def test_start_asks_for_consent(ivan):
    replies = await ivan.send("/start")
    assert "согласие на обработку персональных данных" in replies.text
    assert replies.buttons == [texts.BTN_CONSENT]


async def test_text_before_consent_repeats_consent_request(ivan):
    await ivan.send("/start")
    replies = await ivan.send("привет")
    assert replies.buttons == [texts.BTN_CONSENT]
    assert db.get_client(ivan.id)["consent_at"] is None


async def test_consent_leads_to_name(ivan):
    await ivan.send("/start")
    replies = await ivan.press("consent")
    assert texts.ASK_NAME in replies.text
    assert db.get_client(ivan.id)["consent_at"] is not None


async def test_name_must_be_full(ivan):
    await ivan.send("/start")
    await ivan.press("consent")
    for bad in ("Иванов", "Иванов 123", "Иванов, Иван"):
        replies = await ivan.send(bad)
        assert texts.NAME_INVALID in replies.text, bad
    assert db.get_client(ivan.id)["full_name"] is None


async def test_command_is_not_taken_as_name(ivan):
    await ivan.send("/start")
    await ivan.press("consent")
    await ivan.send("/status")
    assert db.get_client(ivan.id)["full_name"] is None


async def test_name_with_hyphen_and_extra_spaces(ivan):
    await ivan.send("/start")
    await ivan.press("consent")
    await ivan.send("  Салтыков-Щедрин   Михаил  Евграфович ")
    assert db.get_client(ivan.id)["full_name"] == "Салтыков-Щедрин Михаил Евграфович"


async def test_someone_elses_contact_rejected(ivan):
    await ivan.send("/start")
    await ivan.press("consent")
    await ivan.send("Иванов Иван Иванович")
    replies = await ivan.send_contact("79990000000", owner_id=42)
    assert texts.PHONE_NOT_OWN in replies.text
    assert db.get_client(ivan.id)["phone"] is None


async def test_registration_complete(ivan):
    replies = await ivan.register(phone="79991234567")
    assert db.get_client(ivan.id)["phone"] == "+79991234567", "номер сохраняется с плюсом"
    assert "Готово 0 из" in replies.text, "сразу показываем чек-лист"
    assert texts.PHOTO_RULES in replies.text, "и правила съёмки"
    assert texts.BTN_SEND in replies.buttons, "и главное меню"


async def test_start_after_registration_shows_status(ivan):
    await ivan.register()
    replies = await ivan.send("/start")
    assert texts.WELCOME_BACK in replies.text
    assert texts.BTN_CONSENT not in replies.buttons


async def test_registration_continues_after_bot_restart(tg, ivan):
    """Этап регистрации хранится в базе: перезапуск бота (очистка его памяти) не сбрасывает клиента."""
    await ivan.send("/start")
    await ivan.press("consent")
    tg.dp.storage.storage.clear()  # «перезапуск»
    await ivan.send("Иванов Иван Иванович")
    assert db.get_client(ivan.id)["full_name"] == "Иванов Иван Иванович"


async def test_stranger_is_asked_to_press_start(ivan):
    replies = await ivan.send_photo()
    assert texts.NEED_START in replies.text
    assert db.get_client(ivan.id) is None


async def test_unregistered_user_cannot_send_documents(ivan):
    await ivan.send("/start")
    replies = await ivan.send(texts.BTN_SEND)
    assert texts.CHOOSE_DOC not in replies.text
