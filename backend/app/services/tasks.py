import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.db.models import Priority, Source, Status, Task, TranscriptionStatus
from app.schemas.task import TaskUpdate


async def create(
    session: AsyncSession,
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
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def list_tasks(
    session: AsyncSession, user_id: uuid.UUID, status: Status | None = None, q: str | None = None
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if q:
        stmt = stmt.where(Task.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Task.created_at.desc())
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
    session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate
) -> Task:
    task = await get(session, user_id, task_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete(session: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    task = await get(session, user_id, task_id)
    await session.delete(task)
    await session.commit()


async def stats(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    stmt = select(Task.status, func.count()).where(Task.user_id == user_id).group_by(Task.status)
    result = await session.execute(stmt)
    counts = dict.fromkeys((s.value for s in Status), 0)
    for status, count in result.all():
        counts[status] = count
    return counts
