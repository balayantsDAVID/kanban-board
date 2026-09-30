import asyncio

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue_transcription(task_id: str, attempt: int = 1) -> None:
    pool = await get_pool()
    await pool.enqueue_job(
        "transcribe",
        task_id,
        attempt,
        _queue_name="transcription",
        _job_id=f"transcribe:{task_id}:{attempt}",
    )


async def enqueue_notification(chat_id: int, text: str, message_id: int | None = None) -> None:
    # Best-effort, same reasoning as events.publish.
    try:
        pool = await get_pool()
        await pool.enqueue_job(
            "notify",
            chat_id,
            text,
            message_id,
            _queue_name="notifications",
        )
    except (RedisError, OSError):
        logger.warning("side_effect_failed", effect="notify")
