import json
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Task, TaskEvent
from app.schemas.task import TaskOut

logger = get_logger(__name__)


async def publish(redis: Redis, user_id: uuid.UUID, event_type: str, task: Task) -> None:
    envelope = json.dumps(
        {"type": event_type, "task": TaskOut.model_validate(task).model_dump(mode="json")}
    )
    # Best-effort: the DB commit already happened, so a Redis outage must not
    # turn a successful write into an error for the client.
    try:
        await redis.publish(f"events:user:{user_id}", envelope)
    except (RedisError, OSError):
        logger.warning("side_effect_failed", effect="publish", event_type=event_type)


def record(
    session: AsyncSession, task_id: uuid.UUID, type: str, payload: dict | None = None
) -> None:
    """Stage an audit row in the caller's transaction; the caller commits."""
    session.add(TaskEvent(task_id=task_id, type=type, payload=payload or {}))
