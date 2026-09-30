import uuid

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_redis, get_session
from app.db.models import Source, Status, Task
from app.queue.client import enqueue_transcription
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services import tasks as tasks_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
stats_router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: Status | None = None,
    q: str | None = None,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    return await tasks_service.list_tasks(session, user_id, status=status, q=q)


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    body: TaskCreate,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> Task:
    return await tasks_service.create(
        session,
        redis,
        user_id=user_id,
        title=body.title,
        source=Source.WEB,
        description=body.description,
        tags=body.tags,
        priority=body.priority,
        due_at=body.due_at,
    )


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> Task:
    return await tasks_service.update(session, redis, user_id, task_id, body)


@router.post("/{task_id}/retry", response_model=TaskOut)
async def retry_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = await tasks_service.retry(session, user_id, task_id)
    await enqueue_transcription(str(task.id), task.transcription_attempt)
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> None:
    await tasks_service.delete(session, redis, user_id, task_id)


@stats_router.get("/stats")
async def stats(
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    return await tasks_service.stats(session, user_id)
