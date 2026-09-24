from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    project_name: str = "sih-2026 api-service"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://sih:sih@127.0.0.1:5432/numm_ai"

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    ai_service_url: str = "http://localhost:8001"
    ai_service_timeout: float = 60.0

    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "postgresql+asyncpg://sih:sih@127.0.0.1:5432/numm_ai"
        url = v.strip()
        # Automatically adapt Neon / standard postgres URLs to asyncpg
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]

        # For asyncpg URLs, strip query parameters that asyncpg rejects (e.g. sslmode, channel_binding)
        if url.startswith("postgresql+asyncpg://") and "?" in url:
            import urllib.parse
            parsed = urllib.parse.urlsplit(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            # Remove parameters not supported by asyncpg connect
            filtered_params = {
                k: v for k, v in query_params.items() if k not in ("sslmode", "channel_binding")
            }
            new_query = urllib.parse.urlencode(filtered_params, doseq=True)
            url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))

        return url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        return ["http://localhost:3000"]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "t", "debug", "development")
        return bool(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
