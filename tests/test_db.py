"""База: миграции и правила хранения файлов."""
import sqlite3
from datetime import datetime, timedelta, timezone

from bot import db
from conftest import LONG_AGO, set_client


def test_new_database_gets_latest_schema():
    assert db._conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)


def test_old_database_upgraded_without_data_loss(tmp_path, monkeypatch):
    """База фирмы, созданная версией из фазы 1, после обновления бота сохраняет все данные."""
    old = sqlite3.connect(tmp_path / "old.db")
    old.row_factory = sqlite3.Row
    old.executescript(db.MIGRATIONS[0])  # схема фазы 1, версия 0 — как у первых установок
    old.execute("INSERT INTO clients (id, full_name, phone, created_at, last_activity_at) "
                "VALUES (1, 'Иванов', '+7', 'x', 'x')")
    old.execute("INSERT INTO documents VALUES (1, 'passport', 'accepted', NULL, 'x')")
    old.commit()
    monkeypatch.setattr(db, "_conn", old)

    db.init_db()
    db.init_db()  # повторный запуск ничего не ломает

    assert old.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    client = db.get_client(1)
    assert client["full_name"] == "Иванов" and client["reminders_sent"] == 0
    assert db.get_status(1, "passport") == "accepted"


def test_same_file_saved_once_but_allowed_again_after_return():
    db.create_client(1)
    assert db.add_file(1, "passport", "f1", "u1", "photo", None) is True
    assert db.add_file(1, "passport", "f1", "u1", "photo", None) is False, "дубль не сохраняется"
    db.archive_files(1, "passport")  # юрист вернул документ
    assert db.add_file(1, "passport", "f1", "u1", "photo", None) is True, "после возврата тот же файл можно прислать"
    assert db.count_files(1, "passport") == 1


def test_unsubmitted_files_query():
    """«Прислал, но не отправил юристу» — только пока документ не на проверке и клиент молчит."""
    db.create_client(1)
    db.add_file(1, "passport", "f1", "u1", "photo", None)
    db.add_file(1, None, "f2", "u2", "photo", None)
    now = datetime.now(timezone.utc)

    assert db.get_unsubmitted(now - timedelta(minutes=30)) == [], "клиент только что был активен"

    set_client(1, last_activity_at=LONG_AGO)
    rows = {(row["doc_id"], row["files"]) for row in db.get_unsubmitted(now - timedelta(minutes=30))}
    assert rows == {("passport", 1), (None, 1)}

    db.set_status(1, "passport", "review")
    db.mark_unsubmitted_reminded(1)
    assert db.get_unsubmitted(now - timedelta(minutes=30)) == [], "уже напомнили, а паспорт отправлен"
