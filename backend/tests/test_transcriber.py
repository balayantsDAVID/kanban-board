from types import SimpleNamespace

from app.ai.transcriber import FasterWhisperTranscriber


class FakeModel:
    def __init__(self, detected: str) -> None:
        self.detected = detected
        self.languages: list[str | None] = []

    def transcribe(self, _audio: object, language: str | None = None, **_kw: object):
        self.languages.append(language)
        lang = language or self.detected
        return [SimpleNamespace(text=" привет ")], SimpleNamespace(language=lang, duration=1.0)


def _transcriber(model: FakeModel, language: str = "") -> FasterWhisperTranscriber:
    t = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)
    t._model = model  # type: ignore[assignment]
    t._language = language or None
    return t


async def test_unsupported_language_is_redetected_as_russian() -> None:
    model = FakeModel("ar")
    result = await _transcriber(model).transcribe(b"x")
    assert model.languages == [None, "ru"]
    assert result.language == "ru"
    assert result.text == "привет"


async def test_supported_language_is_transcribed_once() -> None:
    model = FakeModel("en")
    result = await _transcriber(model).transcribe(b"x")
    assert model.languages == [None]
    assert result.language == "en"


async def test_language_hint_skips_autodetection() -> None:
    model = FakeModel("ru")
    result = await _transcriber(model, language="ru").transcribe(b"x")
    assert model.languages == ["ru"]
    assert result.language == "ru"
