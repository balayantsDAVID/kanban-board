import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import Priority, Source, Status, TranscriptionStatus


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    tags: list[str] = []
    priority: Priority = Priority.NORMAL
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: Status | None = None
    priority: Priority | None = None
    due_at: datetime | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    tags: list[str]
    status: Status
    priority: Priority
    due_at: datetime | None
    source: Source
    raw_text: str | None
    language: str | None
    transcription_status: TranscriptionStatus
    transcription_error: str | None
    created_at: datetime
    updated_at: datetime
