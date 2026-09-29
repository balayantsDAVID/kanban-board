import uuid

from fastapi import APIRouter, Depends, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_redis, get_session
from app.core.config import Settings, get_settings
from app.core.errors import NotFound
from app.db.models import User
from app.schemas.auth import ExchangeRequest, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/exchange")
async def exchange(
    body: ExchangeRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    token = await auth_service.exchange(redis, settings, body.token)
    response.set_cookie(
        "session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("session", path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(
    user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("user not found")
    return user
