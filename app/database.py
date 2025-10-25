from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.config import Settings, get_settings


_engine: AsyncEngine | None = None
_session_factory: sessionmaker | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            settings.database_url, echo=settings.debug, future=True
        )
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker:
    global _session_factory
    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


@asynccontextmanager
async def get_session(settings: Settings | None = None) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(settings)
    session: AsyncSession = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def create_db_and_tables(settings: Settings | None = None) -> None:
    engine = get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def set_engine(engine: AsyncEngine) -> None:
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
