from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

from app.config import Settings, get_settings
from app.database import set_engine


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def test_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Settings, None]:
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TEST_MODE", "true")
    get_settings.cache_clear()
    settings = get_settings()
    engine: AsyncEngine = create_async_engine(db_url, future=True)
    set_engine(engine)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield settings
    finally:
        await engine.dispose()
        get_settings.cache_clear()
