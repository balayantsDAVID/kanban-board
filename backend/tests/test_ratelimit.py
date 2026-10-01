import uuid

import pytest
from redis.asyncio import Redis

from app.services import ratelimit
from app.services.ratelimit import check_voice_rate


@pytest.fixture(autouse=True)
def _pin_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ratelimit, "_clock", lambda: 1_000_000.0)


async def test_under_limit_allowed(redis: Redis) -> None:
    user_id = uuid.uuid4()
    for _ in range(5):
        assert await check_voice_rate(redis, user_id, limit=5)


async def test_over_limit_rejected(redis: Redis) -> None:
    user_id = uuid.uuid4()
    for _ in range(5):
        await check_voice_rate(redis, user_id, limit=5)
    assert not await check_voice_rate(redis, user_id, limit=5)
