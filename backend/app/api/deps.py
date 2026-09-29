import uuid
from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.errors import Unauthorized
from app.db.session import get_session  # noqa: F401  # re-exported for routes
from app.services.auth import decode_session

__all__ = ["get_session", "get_redis", "current_user"]


@lru_cache
def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url)


async def get_redis() -> AsyncIterator[Redis]:
    yield _redis_client()


async def current_user(request: Request, settings: Settings = Depends(get_settings)) -> uuid.UUID:
    token = request.cookies.get("session")
    if not token:
        raise Unauthorized("missing session")
    return decode_session(settings, token)
