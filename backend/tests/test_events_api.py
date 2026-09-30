import asyncio

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.events import _stream
from app.db.models import Source, User
from app.services import tasks as tasks_service

# httpx's ASGITransport buffers a whole response before returning any of it,
# so it can't exercise a genuinely infinite stream end-to-end. We drive the
# generator directly instead, which is what actually matters here: does a
# publish() land as a well-formed SSE line for a subscriber already listening.


async def test_stream_yields_task_created_event(
    session: AsyncSession, user: User, redis: Redis
) -> None:
    gen = _stream(redis, user.id)
    await gen.__anext__()  # first read after subscribing is a stray "no message yet" tick
    await asyncio.sleep(0.1)

    task = await tasks_service.create(
        session, redis, user_id=user.id, title="wash the car", source=Source.WEB
    )

    line = await asyncio.wait_for(gen.__anext__(), timeout=5)
    assert line.startswith("event: task.created\n")
    assert str(task.id) in line
    assert "wash the car" in line
    await gen.aclose()
