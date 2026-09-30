import json
import uuid

from redis.asyncio import Redis

from app.db.models import Task
from app.schemas.task import TaskOut


async def publish(redis: Redis, user_id: uuid.UUID, event_type: str, task: Task) -> None:
    envelope = json.dumps(
        {"type": event_type, "task": TaskOut.model_validate(task).model_dump(mode="json")}
    )
    await redis.publish(f"events:user:{user_id}", envelope)
