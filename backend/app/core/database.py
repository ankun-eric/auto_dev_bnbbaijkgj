from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _build_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        # SQLite (aiosqlite) is used in tests; pool_size/max_overflow/init_command are MySQL-only.
        return create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
        connect_args={"init_command": "SET time_zone='+00:00'"},
    )


engine = _build_engine()

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
