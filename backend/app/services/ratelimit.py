import time
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError


async def check_voice_rate(redis: Redis, user_id: uuid.UUID, limit: int) -> bool:
    """True if under the per-minute voice limit. Fails open if Redis is unreachable."""
    minute = int(time.time() // 60)
    key = f"voice:{user_id}:{minute}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
    except RedisError:
        return True
    return count <= limit
