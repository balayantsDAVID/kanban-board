from datetime import UTC, datetime

from app.ai.extractor import RulesExtractor
from app.db.models import Priority


async def test_extracts_tags_priority_and_due_date() -> None:
    now = datetime(2025, 6, 10, 9, 0, tzinfo=UTC)
    draft = await RulesExtractor().extract("Купить молоко завтра, срочно #дом", now)

    assert draft.priority == Priority.URGENT
    assert draft.tags == ["дом"]
    assert draft.due_at is not None
    assert draft.due_at.day == 11
    assert "молоко" in draft.title.lower()
    assert "срочно" not in draft.title.lower()
    assert "завтра" not in draft.title.lower()


async def test_defaults_to_normal_priority_without_keywords() -> None:
    now = datetime(2025, 6, 10, 9, 0, tzinfo=UTC)
    draft = await RulesExtractor().extract("Позвонить маме", now)

    assert draft.priority == Priority.NORMAL
    assert draft.tags == []
    assert draft.title == "Позвонить маме"


async def test_high_priority_keyword() -> None:
    now = datetime(2025, 6, 10, 9, 0, tzinfo=UTC)
    draft = await RulesExtractor().extract("Важно подготовить отчёт", now)

    assert draft.priority == Priority.HIGH


async def test_title_falls_back_to_original_when_extraction_empties_it() -> None:
    now = datetime(2025, 6, 10, 9, 0, tzinfo=UTC)
    draft = await RulesExtractor().extract("срочно", now)

    assert draft.priority == Priority.URGENT
    assert draft.title


async def test_extract_safe_falls_back_when_extractor_hangs() -> None:
    import asyncio
    from datetime import UTC, datetime

    from app.ai.extractor import extract_safe

    class Hung:
        async def extract(self, text: str, now: datetime):
            await asyncio.sleep(10)

    draft = await extract_safe(Hung(), "buy milk", datetime.now(UTC), timeout=0.05)  # type: ignore[arg-type]
    assert draft.title == "buy milk"
