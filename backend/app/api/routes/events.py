import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.api.deps import current_user, get_redis

router = APIRouter(prefix="/api", tags=["events"])

PING_INTERVAL_SEC = 15


async def _stream(redis: Redis, user_id: uuid.UUID) -> AsyncIterator[str]:
    pubsub = redis.pubsub()
    channel = f"events:user:{user_id}"
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=PING_INTERVAL_SEC
            )
            if message is None:
                yield ": ping\n\n"
                continue
            envelope = json.loads(message["data"])
            yield f"event: {envelope['type']}\ndata: {json.dumps(envelope['task'])}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.get("/events")
async def stream_events(
    user_id: uuid.UUID = Depends(current_user),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    return StreamingResponse(
        _stream(redis, user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
