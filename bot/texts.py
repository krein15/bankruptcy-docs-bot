"""Все тексты бота. Чтобы переделать бота под фирму, правьте этот файл и checklist.json."""
from html import escape

from bot.checklist import CHECKLIST, progress

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

COMMANDS = [
    ("start", "Главное меню"),
    ("status", "Мои документы"),
]

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
    "• Лучше скан. Если сканера нет — фото на белом листе А4\n"
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
    "Пришлите фото или файлы — можно несколько сразу. Когда закончите, нажмите «Готово»."
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

# ---------- статус ----------

ICONS = {None: "⬜", "review": "🕓", "accepted": "✅", "rejected": "❌", "na": "➖"}
STATUS_LEGEND = "\n\n⬜ нужно прислать  🕓 на проверке  ✅ принят  ❌ вернули  ➖ нет документа"


def status_text(statuses: dict) -> str:
    """Чек-лист клиента с иконками статусов и полосой прогресса."""
    lines = []
    for item in CHECKLIST:
        row = statuses.get(item["id"])
        status = row["status"] if row else None
        line = f"{ICONS[status]} {escape(item['title'])}"
        if status is None and not item["required"]:
            line += " <i>(при наличии)</i>"
        if status == "rejected" and row["comment"]:
            line += f"\n      ↳ <i>{escape(row['comment'])}</i>"
        lines.append(line)

    done, total = progress(statuses)
    filled = round(10 * done / total)
    header = f"<b>Готово {done} из {total}</b>  {'▓' * filled}{'░' * (10 - filled)}\n\n"
    return header + "\n".join(lines) + STATUS_LEGEND


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
