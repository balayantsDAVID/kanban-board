from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str

    telegram_bot_token: str

    jwt_secret: str
    session_ttl_days: int = 30
    web_url: str = "http://localhost:8080"
    cookie_secure: bool = False

    app_tz: str = "Asia/Yerevan"
    log_level: str = "info"
    log_format: Literal["json", "console"] = "json"

    transcriber: Literal["faster_whisper", "openai", "fake"] = "faster_whisper"
    whisper_model: str = "small"
    whisper_threads: int = 4
    voice_max_sec: int = 300

    extractor: Literal["rules", "llm", "fake"] = "rules"
    openai_api_key: str | None = None

    version: str = "dev"
    commit_sha: str = "local"
    build_time: str = ""

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError("jwt_secret must be at least 32 characters")
        return self

    @model_validator(mode="after")
    def _check_openai_key(self) -> "Settings":
        needs_key = self.transcriber == "openai" or self.extractor == "llm"
        if needs_key and not self.openai_api_key:
            raise ValueError("openai_api_key is required when transcriber=openai or extractor=llm")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
