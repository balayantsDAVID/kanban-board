import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import Unauthorized

LOGIN_TOKEN_TTL_SEC = 300


async def issue_login_link(redis: Redis, settings: Settings, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(32)
    await redis.set(f"login:{token}", str(user_id), ex=LOGIN_TOKEN_TTL_SEC)
    return f"{settings.web_url}/login?token={token}"


async def exchange(redis: Redis, settings: Settings, token: str) -> str:
    # GETDEL makes the link single-use: two concurrent requests can't both succeed.
    raw = await redis.getdel(f"login:{token}")
    if raw is None:
        raise Unauthorized("invalid or expired login link")
    user_id = raw.decode() if isinstance(raw, bytes) else raw
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(days=settings.session_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_session(settings: Settings, token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise Unauthorized("invalid session") from exc
    return uuid.UUID(payload["sub"])
