from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.session import get_sessionmaker

logger = get_logger(__name__)
router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    settings = get_settings()
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
        redis = Redis.from_url(settings.redis_url)
        try:
            await redis.ping()
        finally:
            await redis.aclose()
    except Exception as exc:
        logger.warning("not_ready", error=str(exc))
        raise AppError(503, "not_ready", "dependency unavailable") from exc
    return {"status": "ready"}


@router.get("/version")
async def version() -> dict[str, str]:
    settings = get_settings()
    return {
        "version": settings.version,
        "commit": settings.commit_sha,
        "buildTime": settings.build_time,
    }
