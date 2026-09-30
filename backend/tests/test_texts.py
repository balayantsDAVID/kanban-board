import uuid

from app.services import texts


def test_task_transcribed_includes_seconds() -> None:
    msg = texts.task_transcribed(uuid.uuid4(), "Buy milk", "buy milk", 2.345)
    assert "⏱ 2.3 с" in msg
