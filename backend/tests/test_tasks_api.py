import uuid

import pytest
from httpx import AsyncClient


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
