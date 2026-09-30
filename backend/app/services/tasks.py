import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.limits import MAX_ATTEMPTS
from app.db.models import Priority, Source, Status, Task, TranscriptionStatus
from app.schemas.task import TaskUpdate
from app.services.events import publish


async def create(
    session: AsyncSession,
    redis: Redis,
    *,
    user_id: uuid.UUID,
    title: str,
    source: Source,
    description: str | None = None,
    tags: list[str] | None = None,
    priority: Priority = Priority.NORMAL,
    due_at: datetime | None = None,
    raw_text: str | None = None,
    transcription_status: TranscriptionStatus = TranscriptionStatus.NONE,
    tg_chat_id: int | None = None,
    tg_message_id: int | None = None,
    tg_file_id: str | None = None,
    transcription_attempt: int = 0,
) -> Task:
    task = Task(
        user_id=user_id,
        title=title,
        source=source,
        description=description,
        tags=tags or [],
        priority=priority,
        due_at=due_at,
        raw_text=raw_text,
        transcription_status=transcription_status,
        tg_chat_id=tg_chat_id,
        tg_message_id=tg_message_id,
        tg_file_id=tg_file_id,
        transcription_attempt=transcription_attempt,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    await publish(redis, user_id, "task.created", task)
    return task


async def list_tasks(
    session: AsyncSession,
    user_id: uuid.UUID,
    status: Status | None = None,
    q: str | None = None,
    limit: int = 200,
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if q:
        stmt = stmt.where(Task.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars())


async def get(session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    stmt = select(Task).where(Task.user_id == user_id, Task.id == task_id)
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        # Not raising 403 here: leaking "this id exists but isn't yours" is
        # worse than a plain 404.
        raise NotFound("task not found")
    return task


async def update(
    session: AsyncSession, redis: Redis, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate
) -> Task:
    task = await get(session, user_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    status_changed = "status" in changes and changes["status"] != task.status
    for field, value in changes.items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    await publish(redis, user_id, "task.updated", task)
    if status_changed and task.tg_chat_id is not None:
        from app.bot import texts
        from app.queue.client import enqueue_notification

        await enqueue_notification(task.tg_chat_id, texts.status_changed(task.id, task.status))
    return task


async def delete(
    session: AsyncSession, redis: Redis, user_id: uuid.UUID, task_id: uuid.UUID
) -> None:
    task = await get(session, user_id, task_id)
    await session.delete(task)
    await session.commit()
    await publish(redis, user_id, "task.deleted", task)


async def retry(session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = await get(session, user_id, task_id)
    if task.transcription_status != TranscriptionStatus.FAILED:
        raise Conflict("task is not in a failed state")
    if task.transcription_attempt >= MAX_ATTEMPTS:
        raise Conflict("retry limit reached")
    task.transcription_status = TranscriptionStatus.QUEUED
    task.transcription_error = None
    task.transcription_attempt += 1
    await session.commit()
    await session.refresh(task)
    return task


async def stats(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    stmt = select(Task.status, func.count()).where(Task.user_id == user_id).group_by(Task.status)
    result = await session.execute(stmt)
    counts = dict.fromkeys((s.value for s in Status), 0)
    for status, count in result.all():
        counts[status] = count
    return counts
