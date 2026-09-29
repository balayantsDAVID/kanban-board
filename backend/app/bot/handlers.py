from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.db.models import Source, User
from app.services import auth as auth_service
from app.services import tasks as tasks_service

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(texts.START)


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("login"))
async def login(message: Message, user: User, redis: Redis) -> None:
    link = await auth_service.issue_login_link(redis, get_settings(), user.id)
    await message.answer(texts.login_link(link), disable_web_page_preview=True)


@router.message(F.text)
async def text_task(message: Message, user: User, session: AsyncSession) -> None:
    body = (message.text or "").strip()
    if not body:
        return
    task = await tasks_service.create(
        session,
        user_id=user.id,
        title=body[:120],
        source=Source.TEXT,
        raw_text=body,
        tg_chat_id=message.chat.id,
    )
    await message.answer(texts.task_created(task.id, task.title))
