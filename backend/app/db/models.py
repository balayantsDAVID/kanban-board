import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, BigInteger, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Status(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Source(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    WEB = "web"


class TranscriptionStatus(StrEnum):
    NONE = "none"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="user")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    status: Mapped[Status] = mapped_column(String(20), default=Status.PENDING)
    priority: Mapped[Priority] = mapped_column(String(20), default=Priority.NORMAL)
    due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    source: Mapped[Source] = mapped_column(String(10))
    raw_text: Mapped[str | None] = mapped_column(String(4000))
    language: Mapped[str | None] = mapped_column(String(10))

    transcription_status: Mapped[TranscriptionStatus] = mapped_column(
        String(20), default=TranscriptionStatus.NONE
    )
    transcription_error: Mapped[str | None] = mapped_column(String(500))
    transcription_ms: Mapped[int | None]
    transcription_attempt: Mapped[int] = mapped_column(default=0)

    tg_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    tg_message_id: Mapped[int | None] = mapped_column(BigInteger)
    tg_file_id: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_created", "user_id", "created_at"),
        Index(
            "ix_tasks_transcription_pending",
            "transcription_status",
            "updated_at",
            postgresql_where=text("transcription_status IN ('queued', 'processing')"),
        ),
    )


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
