import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_env(**overrides: str) -> dict[str, str]:
    env = {
        "database_url": "postgresql+asyncpg://app:app@localhost/app",
        "redis_url": "redis://localhost:6379/0",
        "telegram_bot_token": "token",
        "jwt_secret": "x" * 32,
    }
    env.update(overrides)
    return env


def test_valid_settings_load() -> None:
    settings = Settings(**_base_env())  # type: ignore[arg-type]
    assert settings.transcriber == "faster_whisper"


def test_short_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**_base_env(jwt_secret="short"))  # type: ignore[arg-type]


def test_openai_transcriber_without_key_rejected() -> None:
    with pytest.raises(ValidationError, match="openai_api_key"):
        Settings(**_base_env(transcriber="openai"))  # type: ignore[arg-type]


def test_llm_extractor_without_key_rejected() -> None:
    with pytest.raises(ValidationError, match="openai_api_key"):
        Settings(**_base_env(extractor="llm"))  # type: ignore[arg-type]


def test_https_web_url_without_secure_cookie_rejected() -> None:
    with pytest.raises(ValidationError, match="cookie_secure"):
        Settings(**_base_env(web_url="https://example.com"))  # type: ignore[arg-type]


def test_https_web_url_with_secure_cookie_accepted() -> None:
    settings = Settings(
        **_base_env(web_url="https://example.com", cookie_secure="true")  # type: ignore[arg-type]
    )
    assert settings.cookie_secure is True
