import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from arq import Retry
from arq.connections import RedisSettings
from arq.cron import cron
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.extractor import Extractor, build_extractor
from app.ai.transcriber import Transcriber, build_transcriber
from app.bot import texts
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Task, TranscriptionStatus
from app.db.session import get_sessionmaker
from app.queue.client import enqueue_notification, enqueue_transcription
from app.services.events import publish
from app.worker._bootstrap import ensure_event_loop

ensure_event_loop()

logger = get_logger(__name__)

TRANSCRIBE_TIMEOUT_SEC = 90
STUCK_AFTER_MIN = 5
MAX_TRIES = 3
DOWNLOAD_TIMEOUT_SEC = 30
from app.core.limits import MAX_ATTEMPTS


class _NoSpeech(Exception):
    pass


async def transcribe(ctx: dict[str, Any], task_id: str, attempt: int) -> None:
    sessionmaker = ctx["sessionmaker"]
    redis: Redis = ctx["redis"]
    bot: Bot = ctx["bot"]
    transcriber: Transcriber = ctx["transcriber"]
    extractor: Extractor = ctx["extractor"]

    async with sessionmaker() as session:
        task = await session.get(Task, uuid.UUID(task_id))
        if task is None or task.transcription_status == TranscriptionStatus.DONE:
            return

        task.transcription_status = TranscriptionStatus.PROCESSING
        await session.commit()
        await session.refresh(task)  # updated_at is server-generated
        await publish(redis, task.user_id, "task.updated", task)

        started = time.monotonic()
        try:
            audio_io = await asyncio.wait_for(
                bot.download(task.tg_file_id),  # type: ignore[arg-type]
                DOWNLOAD_TIMEOUT_SEC,
            )
            if audio_io is None:
                raise RuntimeError("telegram returned no file content")
            audio = audio_io.read()
            transcript = await asyncio.wait_for(
                transcriber.transcribe(audio), TRANSCRIBE_TIMEOUT_SEC
            )
            if not transcript.text.strip():
                raise _NoSpeech
            draft = await extractor.extract(transcript.text, datetime.now(UTC))
        except _NoSpeech:
            # Retrying would transcribe the same silence again.
            await _mark_failed(session, redis, task, "no speech detected", texts.NO_SPEECH)
            return
        except Exception as exc:
            logger.warning(
                "transcription_attempt_failed", task_id=task_id, attempt=attempt, error=str(exc)
            )
            if ctx["job_try"] < MAX_TRIES:
                raise Retry(defer=2 ** ctx["job_try"]) from exc
            await _mark_failed(session, redis, task, str(exc))
            return

        task.title = draft.title
        task.tags = draft.tags
        task.priority = draft.priority
        task.due_at = draft.due_at
        task.raw_text = transcript.text
        task.language = transcript.language
        task.transcription_status = TranscriptionStatus.DONE
        task.transcription_ms = int((time.monotonic() - started) * 1000)
        await session.commit()
        await session.refresh(task)
        logger.info(
            "transcription_done",
            task_id=task_id,
            ms=task.transcription_ms,
            audio_sec=transcript.duration_sec,
            language=transcript.language,
        )
        await publish(redis, task.user_id, "task.updated", task)
        if task.tg_chat_id is not None:
            await enqueue_notification(
                task.tg_chat_id,
                texts.task_transcribed(task.id, task.title, transcript.text),
                task.tg_message_id,
            )


async def _mark_failed(
    session: AsyncSession,
    redis: Redis,
    task: Task,
    error: str,
    message: str = texts.TRANSCRIPTION_FAILED,
) -> None:
    task.transcription_status = TranscriptionStatus.FAILED
    task.transcription_error = error[:500]
    await session.commit()
    await session.refresh(task)
    await publish(redis, task.user_id, "task.updated", task)
    if task.tg_chat_id is not None:
        await enqueue_notification(task.tg_chat_id, message, task.tg_message_id)


async def reconcile(ctx: dict[str, Any]) -> None:
    sessionmaker = ctx["sessionmaker"]
    redis: Redis = ctx["redis"]
    cutoff = datetime.now(UTC) - timedelta(minutes=STUCK_AFTER_MIN)

    async with sessionmaker() as session:
        stmt = select(Task).where(
            Task.transcription_status.in_(
                [TranscriptionStatus.QUEUED, TranscriptionStatus.PROCESSING]
            ),
            Task.updated_at < cutoff,
        )
        result = await session.execute(stmt)
        stuck_tasks = list(result.scalars())

        for task in stuck_tasks:
            if task.transcription_attempt >= MAX_ATTEMPTS:
                await _mark_failed(session, redis, task, "gave up after reconciler retries")
                continue
            task.transcription_attempt += 1
            task.transcription_status = TranscriptionStatus.QUEUED
            await session.commit()
            await enqueue_transcription(str(task.id), task.transcription_attempt)
            logger.info("reconciled_stuck_task", task_id=str(task.id))


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["bot"] = Bot(token=settings.telegram_bot_token)
    ctx["redis"] = Redis.from_url(settings.redis_url)
    ctx["sessionmaker"] = get_sessionmaker()
    ctx["transcriber"] = build_transcriber()
    ctx["extractor"] = build_extractor()


async def on_shutdown(ctx: dict[str, Any]) -> None:
    await ctx["bot"].session.close()
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [transcribe]
    cron_jobs = [cron(reconcile, second=0)]
    queue_name = "transcription"
    max_jobs = 1
    max_tries = MAX_TRIES
    job_timeout = 120
    keep_result = 0
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
