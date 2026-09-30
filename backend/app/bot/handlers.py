from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extractor import build_extractor, extract_safe
from app.bot import texts
from app.core.config import get_settings
from app.db.models import Source, TranscriptionStatus, User
from app.queue.client import enqueue_transcription
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
async def text_task(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    body = (message.text or "").strip()
    if not body:
        return
    draft = await extract_safe(build_extractor(), body, datetime.now(UTC))
    task = await tasks_service.create(
        session,
        redis,
        user_id=user.id,
        title=draft.title,
        source=Source.TEXT,
        raw_text=body,
        tags=draft.tags,
        priority=draft.priority,
        due_at=draft.due_at,
        tg_chat_id=message.chat.id,
    )
    await message.answer(texts.task_created(task.id, task.title))


@router.message(F.voice)
async def voice_task(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    voice = message.voice
    assert voice is not None
    settings = get_settings()
    if voice.duration > settings.voice_max_sec:
        await message.answer(texts.VOICE_TOO_LONG)
        return

    ack = await message.answer(texts.VOICE_ACK)
    task = await tasks_service.create(
        session,
        redis,
        user_id=user.id,
        title=texts.VOICE_ACK,
        source=Source.VOICE,
        transcription_status=TranscriptionStatus.QUEUED,
        tg_chat_id=message.chat.id,
        tg_message_id=ack.message_id,
        tg_file_id=voice.file_id,
        transcription_attempt=1,
    )
    try:
        await enqueue_transcription(str(task.id), task.transcription_attempt)
    except RedisError:
        await ack.edit_text(texts.REDIS_UNAVAILABLE)
