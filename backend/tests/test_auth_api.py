import uuid

from httpx import AsyncClient
from redis.asyncio import Redis

from app.core.config import get_settings
from app.db.models import User
from app.services import auth as auth_service


async def test_exchange_sets_session_cookie_and_me_works(
    client: AsyncClient, user: User, redis: Redis
) -> None:
    settings = get_settings()
    link = await auth_service.issue_login_link(redis, settings, user.id)
    token = link.split("token=")[1]

    resp = await client.post("/api/auth/exchange", json={"token": token})
    assert resp.status_code == 200
    assert "session" in resp.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)


async def test_reusing_login_token_fails(client: AsyncClient, user: User, redis: Redis) -> None:
    settings = get_settings()
    link = await auth_service.issue_login_link(redis, settings, user.id)
    token = link.split("token=")[1]

    first = await client.post("/api/auth/exchange", json={"token": token})
    assert first.status_code == 200

    second = await client.post("/api/auth/exchange", json={"token": token})
    assert second.status_code == 401


async def test_unknown_login_token_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/exchange", json={"token": str(uuid.uuid4())})
    assert resp.status_code == 401


async def test_me_without_cookie_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
