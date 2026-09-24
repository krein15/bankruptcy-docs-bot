"""Все тексты бота. Чтобы переделать бота под фирму, правьте этот файл и checklist.json."""
from datetime import datetime
from html import escape

from bot.checklist import CHECKLIST, in_review, progress, status_of
from bot.config import TIMEZONE

# ---------- кнопки ----------

BTN_CONSENT = "✅ Согласен"
BTN_PHONE = "📱 Поделиться номером"
BTN_SEND = "📎 Отправить документ"
BTN_STATUS = "📋 Мой статус"
BTN_RULES = "📷 Как фотографировать"
BTN_DONE = "✅ Готово"
BTN_NOT_APPLICABLE = "➖ У меня его нет"
BTN_RESEND = "📎 Отправить заново"
BTN_FILES = "📎 Файлы"
BTN_ACCEPT = "✅ Принять"
BTN_REJECT = "❌ Вернуть"
BTN_SUBMIT = "📤 Отправить юристу: {title} ({count})"
BTN_REMIND = "🔔 Напомнить клиенту"
BTN_ALL_CLIENTS = "⬅️ Все клиенты"
BTN_EXPORT = "📊 Выгрузить в Excel"

COMMANDS = [
    ("start", "Главное меню"),
    ("status", "Мои документы"),
]
# Юрист видит в меню и свои команды
LAWYER_COMMANDS = COMMANDS + [
    ("clients", "Клиенты и их документы"),
    ("export", "Выгрузка в Excel"),
]
# В демо все — и клиенты, и юристы
DEMO_COMMANDS = LAWYER_COMMANDS + [
    ("reset", "Начать демо заново"),
]

# ---------- профиль бота ----------
# DESCRIPTION — в пустом чате до «Начать» («Что умеет этот бот?»), до 512 символов.
# SHORT_DESCRIPTION — в профиле бота и в превью ссылки на него, до 120 символов.

DESCRIPTION = (
    "Помогу собрать документы для процедуры банкротства: покажу, что нужно, приму фото и сканы "
    "и сообщу, если юрист попросит что-то переснять.\n\nНажмите «Начать»."
)
SHORT_DESCRIPTION = "Сбор документов для процедуры банкротства: чек-лист, проверка юристом, напоминания."
DEMO_DESCRIPTION = (
    "Демо бота для юридических фирм, которые ведут банкротство физлиц.\n\n"
    "Клиент присылает документы по чек-листу, бот следит за комплектностью и сам напоминает "
    "о недостающем, юрист проверяет каждый документ в один клик.\n\n"
    "Нажмите «Начать» — вы увидите обе стороны: и клиента, и юриста. "
    "Телефон не нужен. Не отправляйте настоящие документы."
)
DEMO_SHORT_DESCRIPTION = "Демо для юрфирм: сбор документов на банкротство физлиц — чек-лист, проверка юристом, напоминания."

# ---------- демо-режим ----------

DEMO_INTRO = (
    "🧪 <b>Демо-версия бота для юридических фирм</b>\n\n"
    "Вы увидите обе стороны: как клиент присылает документы и как юрист их проверяет. "
    "Сообщения «юристу» будут приходить сюда же.\n\n"
    "⚠️ <b>Не отправляйте настоящие документы</b> — подойдут любые картинки и PDF.\n\n"
    "———\n\n"
)
DEMO_PHONE = "не запрашивается в демо"
DEMO_HINT = (
    "🧪 <b>Вы сейчас и клиент, и юрист.</b>\n\n"
    "1. Нажмите «📎 Отправить документ», выберите паспорт, пришлите любую картинку, нажмите «Готово».\n"
    "2. Сюда же придёт уведомление юриста — попробуйте «Принять» или «Вернуть».\n"
    "3. Команды юриста: /clients — все клиенты (с вымышленными для примера), "
    "/export — выгрузка в Excel.\n\n"
    "Начать заново — /reset"
)
DEMO_RESET_DONE = "Ваши демо-данные удалены. Нажмите /start, чтобы пройти заново."
DEMO_NEW_VISITOR = "👀 Демо открыл новый посетитель: {name}"
DEMO_FAKE_REMIND = "Это вымышленный клиент для примера — ему напоминание не уйдёт. Откройте свою карточку и нажмите «Напомнить» там."

# ---------- регистрация ----------

START = (
    "Здравствуйте! Я помогу собрать документы для процедуры банкротства.\n\n"
    "Вы присылаете документы по списку, я слежу, что уже есть, а чего не хватает. "
    "Юрист проверит каждый документ и, если что-то не так, напишет здесь, что исправить.\n\n"
    "Нажимая «Согласен», вы даёте согласие на обработку персональных данных (152-ФЗ) "
    "для подготовки дела о банкротстве."
)
ASK_NAME = "Спасибо. Напишите фамилию, имя и отчество полностью — как в паспорте."
NAME_INVALID = "Не похоже на ФИО. Напишите фамилию, имя и отчество полностью, например: Иванов Иван Иванович"
ASK_PHONE = (
    "И последнее — телефон, чтобы юрист мог с вами связаться. "
    f"Нажмите кнопку «{BTN_PHONE}» внизу экрана."
)
PHONE_NOT_OWN = f"Это чужой контакт. Нажмите кнопку «{BTN_PHONE}» — она отправит ваш номер."
REGISTERED = "Готово, всё настроено. Вот что нужно собрать:\n\n"
WELCOME_BACK = "С возвращением! Ваши документы:\n\n"
NEED_START = "Чтобы начать, нажмите /start"

PHOTO_RULES = (
    "📷 <b>Как фотографировать документы</b>\n\n"
    "Суд не принимает нечитаемые копии: из-за плохого фото заседание могут отложить на месяцы.\n\n"
    "• Лучше скан в PDF. Если сканера нет — фото на белом листе А4\n"
    "• PDF отправляйте через 📎 → «Файл»: в галерее видны только фото\n"
    "• Одно фото — один разворот\n"
    "• Без пальцев на документе, без бликов и теней\n"
    "• Каждая буква и цифра должна читаться\n"
    "• Перед съёмкой протрите камеру"
)

# ---------- отправка документов ----------

CHOOSE_DOC = "Какой документ отправляете?"
NOTHING_TO_SEND = "Все документы приняты юристом — больше ничего присылать не нужно 🎉"
UPLOAD_PROMPT = (
    "<b>{title}</b>\n{description}\n\n"
    "Пришлите фото или сканы — можно несколько сразу. Когда закончите, нажмите «Готово».\n\n"
    "<i>PDF и другие файлы: 📎 → «Файл». В галерее видны только фото.</i>"
)
UPLOAD_OPTIONAL = f"\n\nЕсли такого документа у вас нет — нажмите «{BTN_NOT_APPLICABLE}»."
FILE_RECEIVED = "Получено. Пришлите ещё или нажмите «Готово»."
FILE_DUPLICATE = "Этот файл вы уже присылали."
EXPECT_FILE = "Жду фото или файл. Когда закончите — нажмите «Готово»."
NO_FILES_YET = "Вы ещё не прислали ни одного файла"
SUBMITTED = "📤 <b>{title}</b> — отправлено на проверку ({count}). Юрист ответит здесь."
MARKED_NA = "Отмечено: <b>{title}</b> — такого документа нет."
UNSORTED_ASK = "Файл получен. К какому документу он относится?"
ASSIGNED = "📤 Прикрепил к «{title}» и отправил на проверку ({count})."
NOTHING_TO_ASSIGN = "Неразобранных файлов нет"
STALE_BUTTON = "Эта кнопка устарела"
UNKNOWN = "Пользуйтесь кнопками меню внизу 👇"

# ---------- ответы юриста клиенту ----------

DOC_ACCEPTED = "✅ Юрист принял документ: <b>{title}</b>"
DOC_REJECTED = "❌ Документ нужно прислать заново: <b>{title}</b>\n\nКомментарий юриста: {comment}"
ALL_DONE = "🎉 Все документы собраны и проверены! Юрист свяжется с вами насчёт следующих шагов."

# ---------- напоминания ----------

REMINDER = (
    "👋 Напоминаю про документы для банкротства.\n\n"
    "Осталось:\n{items}\n\n"
    "Чем быстрее соберём всё, тем быстрее юрист подаст заявление в суд."
)
UNSUBMITTED = "Вы прислали файлы, но не отправили их юристу — он их пока не видит. Нажмите кнопку:"
UNSORTED_REMINDER = "У вас есть файлы без пометки — юрист их не видит. К какому документу они относятся?"

# ---------- сторона юриста ----------

NEW_SUBMISSION = (
    "📥 <b>Новые документы на проверку</b>\n\n"
    "Клиент: {name}\n"
    "Телефон: {phone}\n"
    "Документ: <b>{title}</b>\n"
    "Файлов: {count}"
)
FILES_HEADER = "📎 {title} — {name}"
FILES_GONE = "Файлов нет — документ уже вернули клиенту"
ASK_REJECT_REASON = (
    "Что не так с документом «{title}»? Напишите одним сообщением — клиент получит этот текст.\n\n"
    "Передумали — /cancel"
)
MARK_ACCEPTED = "\n\n✅ <b>Принято</b>"
MARK_REJECTED = "\n\n❌ <b>Возвращено:</b> {comment}"
REJECT_SENT = "Отправлено клиенту."
REJECT_CANCELLED = "Отменено. Кнопки под документом по-прежнему работают."
ALREADY_PROCESSED = "Этот документ уже обработан"
CLIENT_COMPLETE = "🎉 {name}: все документы собраны."

NO_CLIENTS = "Пока ни один клиент не прошёл регистрацию."
CLIENTS_HEADER = (
    "👥 <b>Клиенты: {count}</b>\n\n"
    "Сверху — у кого есть документы на проверке (🕓). Нажмите на клиента, чтобы открыть карточку."
)
CLIENTS_TRUNCATED = "\n\nПоказаны первые {shown}. Полный список — в выгрузке Excel."
CLIENT_CARD = (
    "👤 <b>{name}</b>\n"
    "📞 {phone}\n"
    "В боте с {created}\n"
    "Последняя активность: {activity}\n"
    "Напоминаний без ответа: {reminders}\n\n"
)
CLIENT_CARD_FILES_HINT = "\n\nКнопки ниже — документы, по которым есть файлы."
REMINDER_SENT = "Напоминание отправлено"
REMINDER_FAILED = "Не удалось отправить — возможно, клиент заблокировал бота"
NOTHING_TO_REMIND = "У клиента всё собрано — напоминать не о чем"
EXPORT_CAPTION = "📊 Документы клиентов на {date}"
EXPORT_FILENAME = "Документы клиентов {date}.xlsx"

# ---------- статус ----------

ICONS = {None: "⬜", "review": "🕓", "accepted": "✅", "rejected": "❌", "na": "➖"}
STATUS_LEGEND = "\n\n⬜ нужно прислать  🕓 на проверке  ✅ принят  ❌ вернули  ➖ нет документа"

# ---------- Excel ----------

EXPORT_SHEET = "Документы"
EXPORT_HEADERS = ["Клиент", "Телефон", "Последняя активность", "Готово"]
STATUS_LABELS = {
    None: "не прислан",
    "review": "на проверке",
    "accepted": "принят",
    "rejected": "вернули",
    "na": "нет документа",
}
EXPORT_COMMENT_AUTHOR = "Юрист"


def fmt_time(iso: str | None) -> str:
    """Дата из базы (UTC) → время фирмы: 24.09.2026 18:30."""
    if not iso:
        return "—"
    return datetime.fromisoformat(iso).astimezone(TIMEZONE).strftime("%d.%m.%Y %H:%M")


def status_text(statuses: dict) -> str:
    """Чек-лист клиента с иконками статусов и полосой прогресса."""
    lines = []
    for item in CHECKLIST:
        status = status_of(statuses, item["id"])
        line = f"{ICONS[status]} {escape(item['title'])}"
        if status is None and not item["required"]:
            line += " <i>(при наличии)</i>"
        if status == "rejected" and statuses[item["id"]]["comment"]:
            line += f"\n      ↳ <i>{escape(statuses[item['id']]['comment'])}</i>"
        lines.append(line)

    done, total = progress(statuses)
    filled = round(10 * done / total)
    header = f"<b>Готово {done} из {total}</b>  {'▓' * filled}{'░' * (10 - filled)}\n\n"
    return header + "\n".join(lines) + STATUS_LEGEND


def reminder_text(statuses: dict) -> str:
    """Напоминание со списком того, что ещё не прислано или возвращено."""
    lines = []
    for item in CHECKLIST:
        status = status_of(statuses, item["id"])
        if status not in (None, "rejected"):
            continue
        line = f"{ICONS[status]} {escape(item['title'])}"
        if status == "rejected" and statuses[item["id"]]["comment"]:
            line += f" — вернули: <i>{escape(statuses[item['id']]['comment'])}</i>"
        elif not item["required"]:
            line += " <i>(при наличии)</i>"
        lines.append(line)
    return REMINDER.format(items="\n".join(lines))


def client_label(client, statuses: dict) -> str:
    """Подпись кнопки клиента в списке: «Иванов Иван Иванович — 4/12 · 🕓2»."""
    done, total = progress(statuses)
    label = f"{client['full_name']} — {done}/{total}"
    waiting = in_review(statuses)
    return f"{label} · 🕓{waiting}" if waiting else label


def client_card(client, statuses: dict, has_files: bool) -> str:
    text = CLIENT_CARD.format(
        name=escape(client["full_name"]),
        phone=escape(client["phone"]),
        created=fmt_time(client["created_at"]),
        activity=fmt_time(client["last_activity_at"]),
        reminders=client["reminders_sent"],
    ) + status_text(statuses)
    return text + CLIENT_CARD_FILES_HINT if has_files else text


def upload_prompt(item: dict) -> str:
    text = UPLOAD_PROMPT.format(title=escape(item["title"]), description=escape(item["description"]))
    return text if item["required"] else text + UPLOAD_OPTIONAL


def files_count(n: int) -> str:
    """1 файл, 3 файла, 5 файлов."""
    if n % 10 == 1 and n % 100 != 11:
        word = "файл"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "файла"
    else:
        word = "файлов"
    return f"{n} {word}"
