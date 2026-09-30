import json
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.db.models import Task
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
