"""Список документов: настоящий checklist.json корректен, а сломанный бот не пропустит."""
import json

import pytest

from bot import keyboards as kb
from bot.checklist import BY_ID, CHECKLIST, in_review, is_complete, load, progress


def test_real_checklist_is_valid():
    assert CHECKLIST, "список документов пуст"
    assert len(BY_ID) == len(CHECKLIST), "повторяются id"
    for item in CHECKLIST:
        assert item["title"] and item["description"]
        assert isinstance(item["required"], bool)


def test_every_button_fits_telegram_limit():
    """Данные кнопки в Telegram — не больше 64 байт. Проверяем самый длинный случай: большой ID клиента."""
    huge_client_id = 9_999_999_999_999
    for item in CHECKLIST:
        for action in ("upload", "resend", "assign", "submit"):
            assert len(kb.DocCallback(action=action, doc_id=item["id"]).pack().encode()) <= 64
        for action in ("files", "accept", "reject", "open"):
            packed = kb.ReviewCallback(action=action, client_id=huge_client_id, doc_id=item["id"]).pack()
            assert len(packed.encode()) <= 64


def write_checklist(tmp_path, items):
    path = tmp_path / "checklist.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("items, problem", [
    ([{"id": "a", "title": "А", "description": "."}, {"id": "a", "title": "Б", "description": "."}], "повтор id"),
    ([{"id": "паспорт", "title": "Паспорт", "description": "."}], "кириллица в id"),
    ([{"id": "x" * 33, "title": "Паспорт", "description": "."}], "слишком длинный id"),
    ([{"id": "passport", "title": "Паспорт"}], "нет описания"),
])
def test_broken_checklist_stops_bot(tmp_path, items, problem):
    with pytest.raises(SystemExit):
        load(write_checklist(tmp_path, items))


def test_required_by_default(tmp_path):
    items = load(write_checklist(tmp_path, [{"id": "passport", "title": "Паспорт", "description": "."}]))
    assert items[0]["required"] is True


def statuses(**by_doc):
    """{'passport': 'accepted'} → в том виде, в каком статусы приходят из базы."""
    return {doc_id: {"status": status, "comment": None} for doc_id, status in by_doc.items()}


def test_progress_counts_accepted_and_not_applicable():
    assert progress(statuses(passport="accepted", marriage="na", snils="review", inn="rejected")) == (2, len(CHECKLIST))


def test_complete_only_when_every_item_closed():
    all_accepted = statuses(**{item["id"]: "accepted" for item in CHECKLIST})
    assert is_complete(all_accepted)
    all_accepted["passport"] = {"status": "review", "comment": None}
    assert not is_complete(all_accepted)


def test_in_review_ignores_documents_removed_from_checklist():
    assert in_review(statuses(passport="review", old_removed_doc="review")) == 1
