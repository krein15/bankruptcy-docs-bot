"""Вымышленные клиенты — чтобы список клиентов, карточки и Excel выглядели живыми на скриншотах и в демо.

Запуск из папки проекта:
    .venv\\Scripts\\python -m scripts.seed_demo           добавить (повторный запуск пересоздаёт)
    .venv\\Scripts\\python -m scripts.seed_demo --clear   удалить

У вымышленных клиентов отрицательные ID: у настоящих пользователей Telegram ID всегда больше нуля,
поэтому их не перепутать, а напоминания им бот не отправляет.
"""
import sys
from datetime import datetime, timedelta, timezone

from bot import db
from bot.checklist import BY_ID, CHECKLIST

ACCEPTED = ("accepted", None)
REVIEW = ("review", None)
NONE = ("na", None)


def returned(comment: str) -> tuple[str, str]:
    return "rejected", comment


def everything(**overrides) -> dict:
    """Все документы приняты (необязательные — «нет документа»), кроме перечисленных."""
    docs = {item["id"]: ACCEPTED if item["required"] else NONE for item in CHECKLIST}
    return docs | overrides


# ФИО, телефон, сколько часов назад клиент что-то делал, статусы документов
CLIENTS = [
    ("Смирнова Анна Викторовна", "+79000000001", 3, everything(marriage=ACCEPTED, children=ACCEPTED)),
    ("Кузнецов Дмитрий Олегович", "+79000000002", 1, {
        "passport": ACCEPTED, "snils": ACCEPTED, "inn": REVIEW,
        "income": returned("Справка за прошлый год — нужна за текущий"),
    }),
    ("Попова Елена Сергеевна", "+79000000003", 26, {
        "passport": returned("Нет разворота с регистрацией"), "snils": ACCEPTED, "inn": ACCEPTED,
        "marriage": ACCEPTED, "children": REVIEW, "income": NONE,
    }),
    ("Морозова Ольга Андреевна", "+79000000004", 50, everything(property=REVIEW, deals=REVIEW, marriage=ACCEPTED)),
    ("Новиков Сергей Павлович", "+79000000005", 120, {"passport": ACCEPTED}),
    ("Васильев Игорь Николаевич", "+79000000006", 0.2, {}),
]


def seed() -> int:
    db.delete_demo_clients()
    now = datetime.now(timezone.utc)
    for number, (name, phone, hours_ago, docs) in enumerate(CLIENTS, start=1):
        client_id = -number
        db.create_client(client_id)
        db.set_consent(client_id)
        db.set_name(client_id, name)
        db.set_phone(client_id, phone)
        for doc_id, (status, comment) in docs.items():
            if doc_id in BY_ID:  # у фирмы может быть другой checklist.json
                db.set_status(client_id, doc_id, status, comment)
        db.set_last_activity(client_id, now - timedelta(hours=hours_ago))
    return len(CLIENTS)


def main() -> None:
    db.init_db()
    if "--clear" in sys.argv:
        print(f"Удалено вымышленных клиентов: {db.delete_demo_clients()}")
    else:
        print(f"Добавлено вымышленных клиентов: {seed()}")


if __name__ == "__main__":
    main()
