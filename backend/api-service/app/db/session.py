import urllib.parse
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def create_engine_from_url(url: str, debug: bool = False) -> AsyncEngine:
    """Create a configured AsyncEngine with appropriate connection arguments."""
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": debug,
        "future": True,
    }

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        # PostgreSQL / Neon configuration
        parsed = urllib.parse.urlsplit(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        is_ssl = (
            "neon.tech" in parsed.netloc
            or "ssl=require" in url
            or "ssl" in query_params
            or "sslmode" in query_params
        )
        if is_ssl:
            connect_args["ssl"] = "require"

        # Serverless connection pool resilience
        engine_kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        )

    engine_kwargs["connect_args"] = connect_args
    return create_async_engine(url, **engine_kwargs)


engine = create_engine_from_url(settings.database_url, debug=settings.debug)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        yield session

