"""Тексты: склонения, прогресс, экранирование, часовой пояс."""
import pytest

from bot import texts
from bot.checklist import CHECKLIST


@pytest.mark.parametrize("n, expected", [
    (1, "1 файл"), (2, "2 файла"), (4, "4 файла"), (5, "5 файлов"), (11, "11 файлов"),
    (12, "12 файлов"), (14, "14 файлов"), (21, "21 файл"), (22, "22 файла"), (111, "111 файлов"),
])
def test_files_count_declension(n, expected):
    assert texts.files_count(n) == expected


def test_status_text_shows_progress_and_escaped_comment():
    text = texts.status_text({
        "passport": {"status": "accepted", "comment": None},
        "snils": {"status": "rejected", "comment": "Не видно <номер>"},
    })
    assert f"Готово 1 из {len(CHECKLIST)}" in text
    assert "✅ Паспорт" in text and "❌ СНИЛС" in text
    assert "Не видно &lt;номер&gt;" in text, "комментарий юриста должен экранироваться, иначе Telegram не примет HTML"


def test_status_text_marks_optional_documents():
    text = texts.status_text({})
    optional = next(item for item in CHECKLIST if not item["required"])
    assert f"{optional['title']} <i>(при наличии)</i>" in text


def test_reminder_lists_only_missing_and_rejected():
    text = texts.reminder_text({
        "passport": {"status": "accepted", "comment": None},
        "snils": {"status": "review", "comment": None},
        "inn": {"status": "rejected", "comment": "Размыто"},
    })
    assert "Паспорт" not in text and "СНИЛС" not in text
    assert "❌ ИНН — вернули: <i>Размыто</i>" in text


def test_time_shown_in_firm_timezone():
    assert texts.fmt_time("2026-09-24T17:00:00+00:00") == "24.09.2026 20:00"  # Москва = UTC+3
    assert texts.fmt_time(None) == "—"
