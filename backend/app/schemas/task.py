import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.db.models import Priority, Source, Status, TranscriptionStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=2000)]
Tags = Annotated[list[Annotated[str, Field(max_length=50)]], Field(max_length=10)]


class TaskCreate(BaseModel):
    title: Title
    description: Description | None = None
    tags: Tags = []
    priority: Priority = Priority.NORMAL
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: Title | None = None
    description: Description | None = None
    tags: Tags | None = None
    status: Status | None = None
    priority: Priority | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def _non_nullable_fields(self) -> "TaskUpdate":
        # These columns are NOT NULL; an explicit null would surface as a 500.
        for name in ("title", "status", "priority", "tags"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


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
