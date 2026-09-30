from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from arq import Retry
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import get_logger, setup_from_settings
from app.worker._bootstrap import ensure_event_loop

logger = get_logger(__name__)
ensure_event_loop()


async def notify(ctx: dict[str, Any], chat_id: int, text: str, message_id: int | None) -> None:
    bot: Bot = ctx["bot"]
    try:
        if message_id is not None:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
        else:
            await bot.send_message(chat_id, text)
    except TelegramRetryAfter as exc:
        raise Retry(defer=exc.retry_after) from exc
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def on_startup(ctx: dict[str, Any]) -> None:
    setup_from_settings()
    ctx["bot"] = Bot(token=get_settings().telegram_bot_token)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    await ctx["bot"].session.close()


class WorkerSettings:
    functions = [notify]
    queue_name = "notifications"
    max_jobs = 20
    max_tries = 5
    health_check_interval = 30
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
