import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.config import get_settings
from app.db.models import Priority

_HASHTAG_RE = re.compile(r"#(\w+)")
_URGENT_RE = re.compile(r"срочно|urgent|asap|!!+", re.IGNORECASE)
_HIGH_RE = re.compile(r"важно|important", re.IGNORECASE)

MAX_TITLE_LEN = 120


@dataclass
class TaskDraft:
    title: str
    tags: list[str]
    priority: Priority
    due_at: datetime | None


class Extractor(Protocol):
    async def extract(self, text: str, now: datetime) -> TaskDraft: ...


class RulesExtractor:
    async def extract(self, text: str, now: datetime) -> TaskDraft:
        working = text
        tags = _HASHTAG_RE.findall(working)
        working = _HASHTAG_RE.sub("", working)

        priority = Priority.NORMAL
        if _URGENT_RE.search(working):
            priority = Priority.URGENT
            working = _URGENT_RE.sub("", working)
        elif _HIGH_RE.search(working):
            priority = Priority.HIGH
            working = _HIGH_RE.sub("", working)

        due_at, working = self._extract_due_date(working, now)

        title = self._clean_title(working) or self._clean_title(text)
        return TaskDraft(title=title, tags=tags, priority=priority, due_at=due_at)

    def _extract_due_date(self, text: str, now: datetime) -> tuple[datetime | None, str]:
        import dateparser.search

        matches = dateparser.search.search_dates(
            text,
            languages=["ru", "en"],
            settings={
                "TIMEZONE": get_settings().app_tz,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": now,
            },
        )
        if not matches:
            return None, text
        phrase, due_at = matches[0]
        return due_at, text.replace(phrase, "")

    def _clean_title(self, text: str) -> str:
        title = re.sub(r"[,\s]+", " ", text).strip(" ,.")
        title = re.sub(r"^[,\s]+", "", title)
        if title:
            title = title[0].upper() + title[1:]
        return title[:MAX_TITLE_LEN]


class LLMExtractor:
    def __init__(self, api_key: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=5.0)
        self._fallback = RulesExtractor()

    async def extract(self, text: str, now: datetime) -> TaskDraft:
        try:
            return await self._extract_via_llm(text, now)
        except Exception:
            return await self._fallback.extract(text, now)

    async def _extract_via_llm(self, text: str, now: datetime) -> TaskDraft:
        import json

        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract a task from the user's message. Reply with JSON: "
                        '{"title": str, "tags": [str], '
                        '"priority": "low"|"normal"|"high"|"urgent", '
                        '"due_at": ISO8601 datetime or null}. '
                        f"Current time is {now.isoformat()}."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        due_at = datetime.fromisoformat(data["due_at"]) if data.get("due_at") else None
        return TaskDraft(
            title=str(data.get("title", text))[:MAX_TITLE_LEN],
            tags=list(data.get("tags", [])),
            priority=Priority(data.get("priority", "normal")),
            due_at=due_at,
        )


class FakeExtractor:
    async def extract(self, text: str, now: datetime) -> TaskDraft:
        return TaskDraft(title=text[:MAX_TITLE_LEN], tags=[], priority=Priority.NORMAL, due_at=None)


def build_extractor() -> Extractor:
    settings = get_settings()
    if settings.extractor == "llm":
        assert settings.openai_api_key
        return LLMExtractor(settings.openai_api_key)
    if settings.extractor == "fake":
        return FakeExtractor()
    return RulesExtractor()
