import uuid

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


async def test_create_list_update_delete_task(auth_client: AsyncClient) -> None:
    create = await auth_client.post("/api/tasks", json={"title": "Buy milk"})
    assert create.status_code == 201
    task_id = create.json()["id"]
    assert create.json()["status"] == "pending"

    listing = await auth_client.get("/api/tasks")
    assert listing.status_code == 200
    assert any(t["id"] == task_id for t in listing.json())

    patched = await auth_client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "completed"

    deleted = await auth_client.delete(f"/api/tasks/{task_id}")
    assert deleted.status_code == 204

    listing_after = await auth_client.get("/api/tasks")
    assert all(t["id"] != task_id for t in listing_after.json())


async def test_task_of_another_user_is_not_found(auth_client: AsyncClient) -> None:
    resp = await auth_client.patch(f"/api/tasks/{uuid.uuid4()}", json={"title": "x"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_patch_with_invalid_status_is_rejected(auth_client: AsyncClient) -> None:
    create = await auth_client.post("/api/tasks", json={"title": "Buy milk"})
    task_id = create.json()["id"]

    resp = await auth_client.patch(f"/api/tasks/{task_id}", json={"status": "nope"})
    assert resp.status_code == 422


async def test_stats_counts_by_status(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/tasks", json={"title": "A"})
    create = await auth_client.post("/api/tasks", json={"title": "B"})
    await auth_client.patch(f"/api/tasks/{create.json()['id']}", json={"status": "completed"})

    resp = await auth_client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] == 1
    assert body["completed"] == 1


async def test_tasks_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/tasks")
    assert resp.status_code == 401


async def test_redis_publish_failure_does_not_break_writes(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    async def boom(*_a: object, **_kw: object) -> int:
        raise RedisConnectionError("down")

    monkeypatch.setattr(Redis, "publish", boom)
    created = await auth_client.post("/api/tasks", json={"title": "x"})
    assert created.status_code == 201
    patched = await auth_client.patch(
        f"/api/tasks/{created.json()['id']}", json={"status": "completed"}
    )
    assert patched.status_code == 200


@pytest.mark.parametrize(
    "body",
    [{"title": None}, {"status": None}, {"priority": None}, {"title": "x" * 201}, {"title": "  "}],
)
async def test_invalid_patch_is_rejected(auth_client: AsyncClient, body: dict) -> None:
    created = await auth_client.post("/api/tasks", json={"title": "x"})
    resp = await auth_client.patch(f"/api/tasks/{created.json()['id']}", json=body)
    assert resp.status_code == 422


async def test_create_rejects_overlong_title(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/tasks", json={"title": "x" * 201})
    assert resp.status_code == 422


async def test_audit_events_are_recorded(auth_client: AsyncClient, session) -> None:
    from sqlalchemy import text

    created = await auth_client.post("/api/tasks", json={"title": "x"})
    await auth_client.patch(f"/api/tasks/{created.json()['id']}", json={"status": "completed"})
    rows = await session.execute(text("SELECT type FROM task_events ORDER BY created_at"))
    assert [r[0] for r in rows] == ["created", "status_changed"]


async def test_other_users_task_is_invisible(
    auth_client: AsyncClient, session: AsyncSession, redis: Redis
) -> None:
    from app.db.models import Source, User
    from app.services import tasks as tasks_service

    other = User(telegram_id=2, username="other")
    session.add(other)
    await session.commit()
    task = await tasks_service.create(
        session, redis, user_id=other.id, title="x", source=Source.WEB
    )

    url = f"/api/tasks/{task.id}"
    assert (await auth_client.patch(url, json={"title": "y"})).status_code == 404
    assert (await auth_client.delete(url)).status_code == 404
    assert (await auth_client.post(f"{url}/retry")).status_code == 404
    assert (await auth_client.get("/api/tasks")).json() == []


async def test_retry_endpoint(
    auth_client: AsyncClient,
    session: AsyncSession,
    redis: Redis,
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import tasks as routes
    from app.db.models import Source, TranscriptionStatus
    from app.services import tasks as tasks_service

    queued = []

    async def fake_enqueue(task_id: str, attempt: int = 1) -> None:
        queued.append(attempt)

    monkeypatch.setattr(routes, "enqueue_transcription", fake_enqueue)
    failed = await tasks_service.create(
        session,
        redis,
        user_id=user.id,
        title="v",
        source=Source.VOICE,
        transcription_status=TranscriptionStatus.FAILED,
        transcription_attempt=1,
    )
    resp = await auth_client.post(f"/api/tasks/{failed.id}/retry")
    assert resp.status_code == 200
    assert resp.json()["transcription_status"] == "queued"
    assert queued == [2]
    assert (await auth_client.post(f"/api/tasks/{failed.id}/retry")).status_code == 409
