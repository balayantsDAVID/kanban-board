"""add enum check constraints

Revision ID: b2c3d4e5f601
Revises: 9aa27a6580fc
Create Date: 2026-10-01 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f601"
down_revision: str | None = "9aa27a6580fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = {
    "ck_tasks_status_valid": "status IN ('pending', 'in_progress', 'completed')",
    "ck_tasks_priority_valid": "priority IN ('low', 'normal', 'high', 'urgent')",
    "ck_tasks_source_valid": "source IN ('text', 'voice', 'web')",
    "ck_tasks_transcription_status_valid": (
        "transcription_status IN ('none', 'queued', 'processing', 'done', 'failed')"
    ),
}


def upgrade() -> None:
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(name), "tasks", condition)


def downgrade() -> None:
    for name in CHECKS:
        op.drop_constraint(op.f(name), "tasks", type_="check")
