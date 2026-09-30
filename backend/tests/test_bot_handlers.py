from types import SimpleNamespace

import pytest
from arq import Retry
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import handlers
from app.db.models import Source, Status, Task, TranscriptionStatus, User
from app.services import tasks as tasks_service
from app.services import texts
from app.worker import notifications


class StubMessage:
    def __init__(self, text: str | None = None, voice: object | None = None) -> None:
        self.text = text
        self.voice = voice
        self.chat = SimpleNamespace(id=7)
        self.answers: list[str] = []
        self.edits: list[str] = []

    async def edit_text(self, text: str, **_kw: object) -> None:
        self.edits.append(text)

    async def answer(self, text: str, **_kw: object) -> "StubMessage":
        self.answers.append(text)
        ack = StubMessage()
        ack.message_id = 99  # type: ignore[attr-defined]

        async def edit_text(t: str) -> None:
            self.edits.append(t)

        ack.edit_text = edit_text  # type: ignore[method-assign,assignment]
        return ack


async def test_text_message_creates_task(session: AsyncSession, user: User, redis: Redis) -> None:
    msg = StubMessage(text="buy milk #home")
    await handlers.text_task(msg, user, session, redis)  # type: ignore[arg-type]
    task = (await session.execute(select(Task))).scalar_one()
    assert task.tags == ["home"]
    assert len(msg.answers) == 1


async def test_voice_message_queues_with_first_attempt(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    queued = []

    async def fake_enqueue(task_id: str, attempt: int = 1) -> None:
        queued.append(attempt)

    monkeypatch.setattr(handlers, "enqueue_transcription", fake_enqueue)
    msg = StubMessage(voice=SimpleNamespace(duration=3, file_id="f"))
    await handlers.voice_task(msg, user, session, redis)  # type: ignore[arg-type]
    task = (await session.execute(select(Task))).scalar_one()
    assert task.transcription_attempt == 1
    assert task.transcription_status == TranscriptionStatus.QUEUED
    assert queued == [1]


async def test_voice_message_reports_redis_down(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_a: object, **_kw: object) -> None:
        raise RedisConnectionError("down")

    monkeypatch.setattr(handlers, "enqueue_transcription", boom)
    msg = StubMessage(voice=SimpleNamespace(duration=3, file_id="f"))
    await handlers.voice_task(msg, user, session, redis)  # type: ignore[arg-type]
    assert msg.edits == [texts.REDIS_UNAVAILABLE]


class StubCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = StubMessage()
        self.message.edits = []
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


async def test_tasks_command_lists_open_tasks(
    session: AsyncSession, user: User, redis: Redis
) -> None:
    task = await tasks_service.create(
        session, redis, user_id=user.id, title="buy milk", source=Source.TEXT
    )
    msg = StubMessage()
    await handlers.list_tasks(msg, user, session)  # type: ignore[arg-type]
    assert str(task.id)[:8] in msg.answers[0]


async def test_tasks_command_reports_no_open_tasks(session: AsyncSession, user: User) -> None:
    msg = StubMessage()
    await handlers.list_tasks(msg, user, session)  # type: ignore[arg-type]
    assert msg.answers == [texts.NO_OPEN_TASKS]


async def test_status_callback_updates_task_without_duplicate_notification(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = await tasks_service.create(
        session, redis, user_id=user.id, title="buy milk", source=Source.TEXT
    )

    notified = []

    async def fake_enqueue(chat_id: int, text: str, message_id: int | None = None) -> None:
        notified.append(text)

    monkeypatch.setattr(tasks_service, "enqueue_notification", fake_enqueue)
    cb = StubCallback(f"st:{task.id}:c")
    await handlers.status_callback(cb, user, session, redis)  # type: ignore[arg-type]
    await session.refresh(task)
    assert task.status == Status.COMPLETED
    assert notified == []
    assert cb.answered


async def test_notify_retries_on_flood_control() -> None:
    from aiogram.exceptions import TelegramRetryAfter

    class Bot:
        async def send_message(self, *_a: object) -> None:
            raise TelegramRetryAfter(method=None, message="flood", retry_after=3)  # type: ignore[arg-type]

    with pytest.raises(Retry):
        await notifications.notify({"bot": Bot()}, 1, "hi", None)


async def test_notify_ignores_not_modified() -> None:
    from aiogram.exceptions import TelegramBadRequest

    class Bot:
        async def edit_message_text(self, *_a: object, **_kw: object) -> None:
            raise TelegramBadRequest(method=None, message="message is not modified")  # type: ignore[arg-type]

    await notifications.notify({"bot": Bot()}, 1, "hi", 5)


async def test_sixth_voice_in_a_minute_is_rate_limited(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def noop(*_a: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(handlers, "enqueue_transcription", noop)
    for _ in range(5):
        msg = StubMessage(voice=SimpleNamespace(duration=3, file_id="f"))
        await handlers.voice_task(msg, user, session, redis)  # type: ignore[arg-type]

    msg = StubMessage(voice=SimpleNamespace(duration=3, file_id="f"))
    await handlers.voice_task(msg, user, session, redis)  # type: ignore[arg-type]
    assert msg.answers == [texts.RATE_LIMITED]
    count = (await session.execute(select(Task))).scalars().all()
    assert len(count) == 5


async def test_voice_placeholder_title_has_no_duplicate_emoji(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def noop(*_a: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(handlers, "enqueue_transcription", noop)
    msg = StubMessage(voice=SimpleNamespace(duration=3, file_id="f"))
    await handlers.voice_task(msg, user, session, redis)  # type: ignore[arg-type]
    task = (await session.execute(select(Task))).scalar_one()
    assert "🎤" not in task.title
