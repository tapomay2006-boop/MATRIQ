"""Database connection: the engine, the session, and the Base every model inherits."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Parent of every table in app/models/."""


engine = create_async_engine(
    settings.sqlalchemy_url,
    echo=settings.db_echo,
    future=True,
    connect_args=settings.connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request."""
    async with AsyncSessionLocal() as session:
        yield session
