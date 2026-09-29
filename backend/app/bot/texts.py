import uuid

START = (
    "👋 Привет! Я превращаю текст и голосовые сообщения в задачи.\n\n"
    "Просто напиши задачу или запиши голосовое.\n\n"
    "/login — получить ссылку на дашборд\n"
    "/help — список команд"
)

HELP = "Напиши задачу текстом или голосом.\n/login — ссылка для входа в дашборд"

REDIS_UNAVAILABLE = "⚠️ Сервис перегружен, попробуй чуть позже."


def login_link(link: str) -> str:
    return f"🔑 Открой ссылку, чтобы войти в дашборд (действует 5 минут):\n{link}"


def task_created(task_id: uuid.UUID, title: str) -> str:
    return f"✅ #{str(task_id)[:8]}: {title}"
