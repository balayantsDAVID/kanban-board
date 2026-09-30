import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5433/app_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("COOKIE_SECURE", "false")

_db_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1].split("?")[0]
if not _db_name.endswith("_test"):
    pytest.exit(f"refusing to run tests against non-test database {_db_name!r}", returncode=2)

from app.api.deps import _redis_client  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    # get_engine/_redis_client are process-wide lru_cache singletons, but
    # pytest-asyncio gives each test its own event loop, so a connection
    # opened in a previous test's loop can't be reused here.
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    _redis_client.cache_clear()

    async with get_engine().begin() as conn:
        await conn.execute(text("TRUNCATE users, tasks, task_events RESTART IDENTITY CASCADE"))
    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()
    yield
    await get_engine().dispose()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as s:
        yield s


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> User:
    u = User(telegram_id=1, username="tester", first_name="Test")
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[Redis]:
    r = Redis.from_url(get_settings().redis_url)
    try:
        yield r
    finally:
        await r.aclose()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, user: User, redis: Redis) -> AsyncClient:
    from app.services import auth as auth_service

    settings = get_settings()
    link = await auth_service.issue_login_link(redis, settings, user.id)
    token = link.split("token=")[1]
    resp = await client.post("/api/auth/exchange", json={"token": token})
    assert resp.status_code == 200
    return client


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()
