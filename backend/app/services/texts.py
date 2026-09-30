import uuid

from app.db.models import Status

STATUS_LABELS = {
    Status.PENDING: "Pending",
    Status.IN_PROGRESS: "In Progress",
    Status.COMPLETED: "Completed",
}

START = (
    "👋 Привет! Я превращаю текст и голосовые сообщения в задачи.\n\n"
    "Просто напиши задачу или запиши голосовое.\n\n"
    "/login — получить ссылку на дашборд\n"
    "/help — список команд"
)

HELP = "Напиши задачу текстом или голосом.\n/login — ссылка для входа в дашборд"

REDIS_UNAVAILABLE = "⚠️ Сервис перегружен, попробуй чуть позже."
VOICE_PLACEHOLDER_TITLE = "Распознаю…"
VOICE_ACK = "🎤 Распознаю…"
VOICE_TOO_LONG = "⚠️ Голосовое слишком длинное, пришли короче или напиши текстом."
TRANSCRIPTION_FAILED = "❌ Не смог распознать. Повтори в дашборде или пришли текстом."


NO_SPEECH = "🔇 Не услышал речи в сообщении. Попробуй записать ещё раз или напиши текстом."


def login_link(link: str) -> str:
    # Telegram drops links to hosts without a TLD (localhost), so also show it as copyable text.
    return f'🔑 <a href="{link}">Открыть дашборд</a> (действует 5 минут)\n\n<code>{link}</code>'


def task_created(task_id: uuid.UUID, title: str) -> str:
    return f"✅ #{str(task_id)[:8]}: {title}"


def task_transcribed(task_id: uuid.UUID, title: str, transcript: str, seconds: float) -> str:
    return f"✅ #{str(task_id)[:8]}: {title}\n📝 {transcript}\n⏱ {seconds:.1f} с"


def status_changed(task_id: uuid.UUID, status: Status) -> str:
    return f"🔄 #{str(task_id)[:8]} → {STATUS_LABELS[status]}"


NO_OPEN_TASKS = "Нет открытых задач."


def task_list(tasks: list[tuple[uuid.UUID, str, Status]]) -> str:
    lines = [f"#{str(tid)[:8]} [{STATUS_LABELS[status]}] {title}" for tid, title, status in tasks]
    return "\n".join(lines)
