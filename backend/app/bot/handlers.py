import uuid
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extractor import build_extractor, extract_safe
from app.core.config import get_settings
from app.db.models import Source, Status, TranscriptionStatus, User
from app.queue.client import enqueue_transcription
from app.schemas.task import TaskUpdate
from app.services import auth as auth_service
from app.services import tasks as tasks_service
from app.services import texts

router = Router()

_CALLBACK_STATUS = {"p": Status.PENDING, "i": Status.IN_PROGRESS, "c": Status.COMPLETED}


def _status_keyboard(task_id: object) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶ In Progress", callback_data=f"st:{task_id}:i"),
                InlineKeyboardButton(text="✅ Done", callback_data=f"st:{task_id}:c"),
            ]
        ]
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(texts.START)


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("login"))
async def login(message: Message, user: User, redis: Redis) -> None:
    link = await auth_service.issue_login_link(redis, get_settings(), user.id)
    await message.answer(texts.login_link(link), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("tasks"))
async def list_tasks(message: Message, user: User, session: AsyncSession) -> None:
    open_tasks = [
        t
        for t in await tasks_service.list_tasks(session, user.id, limit=50)
        if t.status != Status.COMPLETED
    ][:10]
    if not open_tasks:
        await message.answer(texts.NO_OPEN_TASKS)
        return
    await message.answer(texts.task_list([(t.id, t.title, t.status) for t in open_tasks]))


@router.callback_query(F.data.startswith("st:"))
async def status_callback(
    callback: CallbackQuery, user: User, session: AsyncSession, redis: Redis
) -> None:
    _, task_id, code = callback.data.split(":")  # type: ignore[union-attr]
    status = _CALLBACK_STATUS[code]
    task = await tasks_service.update(
        session,
        redis,
        user.id,
        uuid.UUID(task_id),
        TaskUpdate(status=status),
        notify=False,
    )
    try:
        await callback.message.edit_text(texts.status_changed(task.id, task.status))  # type: ignore[union-attr]
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
    await callback.answer()


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
        raw_text=body[:4000],
        tags=draft.tags,
        priority=draft.priority,
        due_at=draft.due_at,
        tg_chat_id=message.chat.id,
    )
    await message.answer(
        texts.task_created(task.id, task.title), reply_markup=_status_keyboard(task.id)
    )


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
        title=texts.VOICE_PLACEHOLDER_TITLE,
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
