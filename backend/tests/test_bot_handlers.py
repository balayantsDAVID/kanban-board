from types import SimpleNamespace

import pytest
from arq import Retry
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import handlers
from app.db.models import Task, TranscriptionStatus, User
from app.services import texts
from app.worker import notifications


class StubMessage:
    def __init__(self, text: str | None = None, voice: object | None = None) -> None:
        self.text = text
        self.voice = voice
        self.chat = SimpleNamespace(id=7)
        self.answers: list[str] = []
        self.edits: list[str] = []

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
