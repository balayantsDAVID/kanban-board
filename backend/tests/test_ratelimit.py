import uuid

from redis.asyncio import Redis

from app.services.ratelimit import check_voice_rate


async def test_under_limit_allowed(redis: Redis) -> None:
    user_id = uuid.uuid4()
    for _ in range(5):
        assert await check_voice_rate(redis, user_id, limit=5)


async def test_over_limit_rejected(redis: Redis) -> None:
    user_id = uuid.uuid4()
    for _ in range(5):
        await check_voice_rate(redis, user_id, limit=5)
    assert not await check_voice_rate(redis, user_id, limit=5)
