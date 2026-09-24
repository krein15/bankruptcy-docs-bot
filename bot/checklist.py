"""Список документов из checklist.json — главное, что меняется под каждую фирму."""
import json

from bot.config import BASE_DIR

# Статусы, при которых пункт считается закрытым: принят юристом или документа у клиента нет
DONE_STATUSES = ("accepted", "na")


def _load() -> list[dict]:
    with open(BASE_DIR / "checklist.json", encoding="utf-8") as f:
        items = json.load(f)

    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)):
        raise SystemExit("checklist.json: id документов повторяются")

    for item in items:
        missing = {"id", "title", "description"} - item.keys()
        if missing:
            raise SystemExit(f"checklist.json: у пункта {item} нет полей {missing}")
        # id уходит в данные кнопки, а Telegram ограничивает их 64 байтами
        if not item["id"].isascii() or len(item["id"]) > 32:
            raise SystemExit(f"checklist.json: id «{item['id']}» — только латиница, до 32 символов")
        item.setdefault("required", True)
    return items


CHECKLIST = _load()
BY_ID = {item["id"]: item for item in CHECKLIST}


def status_of(statuses: dict, doc_id: str) -> str | None:
    """Статус документа у клиента; None — ещё не прислан."""
    row = statuses.get(doc_id)
    return row["status"] if row else None


def progress(statuses: dict) -> tuple[int, int]:
    """Сколько пунктов закрыто и сколько всего."""
    done = sum(1 for item in CHECKLIST if status_of(statuses, item["id"]) in DONE_STATUSES)
    return done, len(CHECKLIST)


def in_review(statuses: dict) -> int:
    """Сколько документов ждут проверки юриста."""
    return sum(1 for item in CHECKLIST if status_of(statuses, item["id"]) == "review")


def is_complete(statuses: dict) -> bool:
    done, total = progress(statuses)
    return done == total
