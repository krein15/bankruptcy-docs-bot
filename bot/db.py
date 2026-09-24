"""База SQLite. Все SQL-запросы проекта — только в этом файле."""
import sqlite3
from datetime import datetime, timezone

from bot.config import DB_PATH

# Миграции — изменения схемы по порядку. Номер последней применённой хранится в самой базе
# (PRAGMA user_version), поэтому при обновлении бота у фирмы база дополняется, а не пересоздаётся.
# Правило: старые миграции не меняем, новые — только дописываем в конец.
MIGRATIONS = [
    # 1 — фаза 1: клиенты, статусы документов, файлы
    """
    CREATE TABLE IF NOT EXISTS clients (
        id               INTEGER PRIMARY KEY,  -- Telegram user_id
        full_name        TEXT,
        phone            TEXT,
        consent_at       TEXT,                 -- когда дал согласие на обработку ПДн
        created_at       TEXT NOT NULL,
        last_activity_at TEXT NOT NULL
    );

    -- Статус пункта чек-листа у клиента. Нет строки — документ ещё не прислан.
    CREATE TABLE IF NOT EXISTS documents (
        client_id  INTEGER NOT NULL REFERENCES clients (id),
        doc_id     TEXT NOT NULL,              -- id из checklist.json
        status     TEXT NOT NULL CHECK (status IN ('review', 'accepted', 'rejected', 'na')),
        comment    TEXT,                       -- причина возврата
        updated_at TEXT NOT NULL,
        PRIMARY KEY (client_id, doc_id)
    );

    -- Сами файлы не храним: только file_id, по которому Telegram отдаёт файл заново.
    CREATE TABLE IF NOT EXISTS files (
        id             INTEGER PRIMARY KEY,
        client_id      INTEGER NOT NULL REFERENCES clients (id),
        doc_id         TEXT,                   -- NULL — клиент ещё не сказал, что это за файл
        file_id        TEXT NOT NULL,
        file_unique_id TEXT NOT NULL,          -- одинаков у одного и того же файла, даже пересланного
        kind           TEXT NOT NULL,          -- photo / document
        file_name      TEXT,
        archived       INTEGER NOT NULL DEFAULT 0,  -- 1 — документ вернули, файлы больше не актуальны
        received_at    TEXT NOT NULL
    );

    -- Один и тот же файл не сохраняем дважды (архивные не в счёт)
    CREATE UNIQUE INDEX IF NOT EXISTS files_no_duplicates
        ON files (client_id, file_unique_id) WHERE archived = 0;
    """,
    # 2 — фаза 2: напоминания
    """
    ALTER TABLE clients ADD COLUMN last_reminder_at TEXT;
    ALTER TABLE clients ADD COLUMN reminders_sent INTEGER NOT NULL DEFAULT 0;  -- подряд, без ответа клиента
    ALTER TABLE clients ADD COLUMN unsubmitted_reminded_at TEXT;  -- когда напомнили нажать «Готово»
    """,
]

_conn = sqlite3.connect(DB_PATH)
_conn.row_factory = sqlite3.Row  # строки как словари: row["status"]
_conn.execute("PRAGMA foreign_keys = ON")


def init_db() -> None:
    """Применяет миграции, которых в базе ещё нет."""
    version = _conn.execute("PRAGMA user_version").fetchone()[0]
    for number, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        # BEGIN…COMMIT: миграция и её номер записываются вместе или не записываются вовсе
        _conn.executescript(f"BEGIN; {sql}; PRAGMA user_version = {number}; COMMIT;")


def _now() -> str:
    return _iso(datetime.now(timezone.utc))


def _iso(moment: datetime) -> str:
    # Все даты храним в UTC одной строкой — такие строки можно сравнивать в SQL как текст
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


# ---------- клиенты ----------

def get_client(user_id: int) -> sqlite3.Row | None:
    return _conn.execute("SELECT * FROM clients WHERE id = ?", (user_id,)).fetchone()


def get_clients() -> list[sqlite3.Row]:
    """Клиенты, прошедшие регистрацию, — сначала недавно активные."""
    return _conn.execute(
        "SELECT * FROM clients WHERE phone IS NOT NULL ORDER BY last_activity_at DESC"
    ).fetchall()


def create_client(user_id: int) -> None:
    with _conn:
        _conn.execute(
            "INSERT OR IGNORE INTO clients (id, created_at, last_activity_at) VALUES (?, ?, ?)",
            (user_id, _now(), _now()),
        )


def set_consent(user_id: int) -> None:
    with _conn:
        _conn.execute("UPDATE clients SET consent_at = ? WHERE id = ?", (_now(), user_id))


def set_name(user_id: int, full_name: str) -> None:
    with _conn:
        _conn.execute("UPDATE clients SET full_name = ? WHERE id = ?", (full_name, user_id))


def set_phone(user_id: int, phone: str) -> None:
    with _conn:
        _conn.execute("UPDATE clients SET phone = ? WHERE id = ?", (phone, user_id))


def touch(user_id: int) -> None:
    """Клиент что-то сделал: запоминаем время и обнуляем счётчик напоминаний."""
    with _conn:
        _conn.execute(
            "UPDATE clients SET last_activity_at = ?, reminders_sent = 0 WHERE id = ?", (_now(), user_id)
        )


# ---------- напоминания ----------

def get_clients_to_remind(silent_since: datetime, max_reminders: int) -> list[sqlite3.Row]:
    """Клиенты, которые молчат с silent_since, и с последнего напоминания прошло не меньше."""
    cutoff = _iso(silent_since)
    return _conn.execute(
        """SELECT * FROM clients
           WHERE phone IS NOT NULL
             AND last_activity_at < ?
             AND (last_reminder_at IS NULL OR last_reminder_at < ?)
             AND reminders_sent < ?""",
        (cutoff, cutoff, max_reminders),
    ).fetchall()


def mark_reminded(client_id: int) -> None:
    with _conn:
        _conn.execute(
            "UPDATE clients SET last_reminder_at = ?, reminders_sent = reminders_sent + 1 WHERE id = ?",
            (_now(), client_id),
        )


def get_unsubmitted(silent_since: datetime) -> list[sqlite3.Row]:
    """Файлы, которые клиент прислал, но юристу не отправил (не нажал «Готово» или не выбрал документ).
    Одна строка — клиент + документ (doc_id NULL — неразобранные) + сколько файлов.
    Только если клиент молчит с silent_since и после его последнего действия мы об этом ещё не напоминали."""
    return _conn.execute(
        """SELECT f.client_id, f.doc_id, COUNT(*) AS files
           FROM files f
           JOIN clients c ON c.id = f.client_id
           LEFT JOIN documents d ON d.client_id = f.client_id AND d.doc_id = f.doc_id
           WHERE f.archived = 0
             AND (d.status IS NULL OR d.status IN ('rejected', 'na'))
             AND c.last_activity_at < ?
             AND (c.unsubmitted_reminded_at IS NULL OR c.unsubmitted_reminded_at < c.last_activity_at)
           GROUP BY f.client_id, f.doc_id""",
        (_iso(silent_since),),
    ).fetchall()


def mark_unsubmitted_reminded(client_id: int) -> None:
    with _conn:
        _conn.execute("UPDATE clients SET unsubmitted_reminded_at = ? WHERE id = ?", (_now(), client_id))


# ---------- файлы ----------

def add_file(client_id: int, doc_id: str | None, file_id: str, file_unique_id: str,
             kind: str, file_name: str | None) -> bool:
    """Сохраняет файл. Возвращает False, если такой файл уже был."""
    with _conn:
        cur = _conn.execute(
            """INSERT OR IGNORE INTO files
               (client_id, doc_id, file_id, file_unique_id, kind, file_name, received_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (client_id, doc_id, file_id, file_unique_id, kind, file_name, _now()),
        )
    return cur.rowcount == 1


def get_files(client_id: int, doc_id: str) -> list[sqlite3.Row]:
    return _conn.execute(
        "SELECT * FROM files WHERE client_id = ? AND doc_id = ? AND archived = 0 ORDER BY id",
        (client_id, doc_id),
    ).fetchall()


def count_files(client_id: int, doc_id: str) -> int:
    return _conn.execute(
        "SELECT COUNT(*) FROM files WHERE client_id = ? AND doc_id = ? AND archived = 0",
        (client_id, doc_id),
    ).fetchone()[0]


def count_files_by_doc(client_id: int) -> dict[str, int]:
    """Сколько актуальных файлов у клиента по каждому документу."""
    rows = _conn.execute(
        """SELECT doc_id, COUNT(*) AS files FROM files
           WHERE client_id = ? AND doc_id IS NOT NULL AND archived = 0
           GROUP BY doc_id""",
        (client_id,),
    )
    return {row["doc_id"]: row["files"] for row in rows}


def assign_unsorted(client_id: int, doc_id: str) -> int:
    """Прикрепляет неразобранные файлы клиента к документу. Возвращает, сколько прикрепили."""
    with _conn:
        cur = _conn.execute(
            "UPDATE files SET doc_id = ? WHERE client_id = ? AND doc_id IS NULL AND archived = 0",
            (doc_id, client_id),
        )
    return cur.rowcount


def archive_files(client_id: int, doc_id: str) -> None:
    with _conn:
        _conn.execute(
            "UPDATE files SET archived = 1 WHERE client_id = ? AND doc_id = ? AND archived = 0",
            (client_id, doc_id),
        )


# ---------- статусы документов ----------

def set_status(client_id: int, doc_id: str, status: str, comment: str | None = None) -> None:
    with _conn:
        _conn.execute(
            """INSERT INTO documents (client_id, doc_id, status, comment, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (client_id, doc_id) DO UPDATE SET
                   status = excluded.status,
                   comment = excluded.comment,
                   updated_at = excluded.updated_at""",
            (client_id, doc_id, status, comment, _now()),
        )


def get_status(client_id: int, doc_id: str) -> str | None:
    row = _conn.execute(
        "SELECT status FROM documents WHERE client_id = ? AND doc_id = ?", (client_id, doc_id)
    ).fetchone()
    return row["status"] if row else None


def get_statuses(client_id: int) -> dict[str, sqlite3.Row]:
    """Все статусы клиента: {doc_id: строка со status и comment}."""
    rows = _conn.execute(
        "SELECT doc_id, status, comment FROM documents WHERE client_id = ?", (client_id,)
    )
    return {row["doc_id"]: row for row in rows}


def get_all_statuses() -> dict[int, dict[str, sqlite3.Row]]:
    """Статусы всех клиентов: {client_id: {doc_id: строка}}."""
    result = {}
    for row in _conn.execute("SELECT client_id, doc_id, status, comment FROM documents"):
        result.setdefault(row["client_id"], {})[row["doc_id"]] = row
    return result
