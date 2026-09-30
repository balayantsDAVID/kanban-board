import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import get_settings


@dataclass
class Transcript:
    text: str
    language: str | None
    duration_sec: float | None


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes) -> Transcript: ...


class FasterWhisperTranscriber:
    def __init__(self, model_name: str, threads: int) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(model_name, compute_type="int8", cpu_threads=threads)

    async def transcribe(self, audio: bytes) -> Transcript:
        return await asyncio.to_thread(self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: bytes) -> Transcript:
        import io

        segments, info = self._model.transcribe(io.BytesIO(audio), vad_filter=True, beam_size=1)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return Transcript(text=text, language=info.language, duration_sec=info.duration)


class OpenAITranscriber:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=30.0)

    async def transcribe(self, audio: bytes) -> Transcript:
        import io

        buf = io.BytesIO(audio)
        buf.name = "voice.ogg"
        result = await self._client.audio.transcriptions.create(model="whisper-1", file=buf)
        return Transcript(text=result.text.strip(), language=None, duration_sec=None)


class FakeTranscriber:
    """For tests: returns a fixed transcript, or raises if configured to fail."""

    def __init__(self, text: str = "test transcript", fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls = 0

    async def transcribe(self, audio: bytes) -> Transcript:
        self.calls += 1
        if self.fail:
            raise RuntimeError("transcription failed")
        return Transcript(text=self.text, language="en", duration_sec=1.0)


@lru_cache
def build_transcriber() -> Transcriber:
    settings = get_settings()
    if settings.transcriber == "openai":
        assert settings.openai_api_key
        return OpenAITranscriber(settings.openai_api_key)
    if settings.transcriber == "fake":
        return FakeTranscriber()
    return FasterWhisperTranscriber(settings.whisper_model, settings.whisper_threads)
