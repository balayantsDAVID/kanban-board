from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.session import get_sessionmaker
from app.services import users as users_service


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_sessionmaker()() as session:
            data["session"] = session
            tg_user = data.get("event_from_user")
            if tg_user is not None:
                data["user"] = await users_service.get_or_create(
                    session, tg_user.id, tg_user.username, tg_user.first_name
                )
            return await handler(event, data)
