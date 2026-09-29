import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_session
from app.db.models import Source, Status, Task
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
) -> Task:
    return await tasks_service.create(
        session,
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
) -> Task:
    return await tasks_service.update(session, user_id, task_id, body)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await tasks_service.delete(session, user_id, task_id)


@stats_router.get("/stats")
async def stats(
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    return await tasks_service.stats(session, user_id)
