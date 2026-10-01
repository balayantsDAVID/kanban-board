import time
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

# Indirection so tests can pin the clock: fixed windows reset on minute boundaries.
_clock = time.time


async def check_voice_rate(redis: Redis, user_id: uuid.UUID, limit: int) -> bool:
    """True if under the per-minute voice limit. Fails open if Redis is unreachable."""
    minute = int(_clock() // 60)
    key = f"voice:{user_id}:{minute}"
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
    except RedisError:
        return True
    return count <= limit
