from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session
from app.internal.orchestrator import GameOrchestrator


async def session_dependency(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    async with get_session(settings) as session:
        yield session


def orchestrator_dependency(request: Request) -> GameOrchestrator:
    return _state_attr(request, "orchestrator")


def templates_dependency(request: Request) -> Jinja2Templates:
    return _state_attr(request, "templates")


def _state_attr(request: Request, attr: str):
    value = getattr(request.app.state, attr, None)
    if value is None:
        raise RuntimeError(f"{attr!r} not initialized on application state")
    return value
