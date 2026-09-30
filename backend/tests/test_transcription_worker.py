import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from arq import Retry
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extractor import FakeExtractor
from app.ai.transcriber import FakeTranscriber
from app.db.models import Source, TranscriptionStatus, User
from app.db.session import get_sessionmaker
from app.services import tasks as tasks_service
from app.worker import transcription


class FakeBot:
    async def download(self, _file_id: str) -> io.BytesIO:
        return io.BytesIO(b"audio-bytes")


def _ctx(redis: Redis, transcriber: object, job_try: int = 1) -> dict:
    return {
        "sessionmaker": get_sessionmaker(),
        "redis": redis,
        "bot": FakeBot(),
        "transcriber": transcriber,
        "extractor": FakeExtractor(),
        "job_try": job_try,
    }


async def _voice_task(session: AsyncSession, user: User):
    return await tasks_service.create(
        session,
        user_id=user.id,
        title="🎤 Голосовое…",
        source=Source.VOICE,
        transcription_status=TranscriptionStatus.QUEUED,
        tg_chat_id=1,
        tg_message_id=42,
        tg_file_id="tg-file-id",
    )


async def test_retries_then_fails_after_max_tries(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    notified = []

    async def fake_notify(chat_id, msg, message_id=None):
        notified.append((chat_id, msg))

    monkeypatch.setattr(transcription, "enqueue_notification", fake_notify)
    task = await _voice_task(session, user)
    fake = FakeTranscriber(fail=True)

    with pytest.raises(Retry):
        await transcription.transcribe(_ctx(redis, fake, job_try=1), str(task.id), 1)
    with pytest.raises(Retry):
        await transcription.transcribe(_ctx(redis, fake, job_try=2), str(task.id), 2)

    await transcription.transcribe(_ctx(redis, fake, job_try=3), str(task.id), 3)

    async with get_sessionmaker()() as check_session:
        refreshed = await check_session.get(type(task), task.id)
        assert refreshed.transcription_status == TranscriptionStatus.FAILED
        assert refreshed.transcription_error
    assert len(notified) == 1


async def test_timeout_is_treated_as_failure(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(transcription, "TRANSCRIBE_TIMEOUT_SEC", 0.05)

    class SlowTranscriber:
        async def transcribe(self, _audio: bytes):
            await asyncio.sleep(1)

    task = await _voice_task(session, user)
    with pytest.raises(Retry):
        await transcription.transcribe(_ctx(redis, SlowTranscriber(), job_try=1), str(task.id), 1)


async def test_successful_transcription_is_idempotent_on_replay(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    notified = []

    async def fake_notify(chat_id, msg, message_id=None):
        notified.append((chat_id, msg))

    monkeypatch.setattr(transcription, "enqueue_notification", fake_notify)
    task = await _voice_task(session, user)
    fake = FakeTranscriber(text="buy milk")

    await transcription.transcribe(_ctx(redis, fake, job_try=1), str(task.id), 1)

    async with get_sessionmaker()() as check_session:
        refreshed = await check_session.get(type(task), task.id)
        assert refreshed.transcription_status == TranscriptionStatus.DONE
        assert refreshed.raw_text == "buy milk"
    assert len(notified) == 1

    # Replaying the same job (e.g. a duplicate delivery) must not redo the work.
    await transcription.transcribe(_ctx(redis, fake, job_try=1), str(task.id), 1)
    assert fake.calls == 1
    assert len(notified) == 1


async def test_reconcile_requeues_stuck_task(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    enqueued = []

    async def fake_enqueue(task_id, attempt):
        enqueued.append((task_id, attempt))

    monkeypatch.setattr(transcription, "enqueue_transcription", fake_enqueue)
    task = await _voice_task(session, user)
    old = datetime.now(UTC) - timedelta(minutes=10)
    await session.execute(
        text("UPDATE tasks SET updated_at = :dt WHERE id = :id"), {"dt": old, "id": task.id}
    )
    await session.commit()

    await transcription.reconcile({"sessionmaker": get_sessionmaker(), "redis": redis})

    assert enqueued == [(str(task.id), 1)]


async def test_reconcile_gives_up_after_max_attempts(
    session: AsyncSession, user: User, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_enqueue(*_a, **_kw):
        return None

    monkeypatch.setattr(transcription, "enqueue_transcription", fake_enqueue)
    task = await _voice_task(session, user)
    old = datetime.now(UTC) - timedelta(minutes=10)
    await session.execute(
        text("UPDATE tasks SET updated_at = :dt, transcription_attempt = :n WHERE id = :id"),
        {"dt": old, "n": transcription.MAX_RECONCILE_ATTEMPTS, "id": task.id},
    )
    await session.commit()

    await transcription.reconcile({"sessionmaker": get_sessionmaker(), "redis": redis})

    async with get_sessionmaker()() as check_session:
        refreshed = await check_session.get(type(task), task.id)
        assert refreshed.transcription_status == TranscriptionStatus.FAILED
