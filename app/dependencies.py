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
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return orchestrator


def templates_dependency(request: Request) -> Jinja2Templates:
    templates = getattr(request.app.state, "templates", None)
    if templates is None:
        raise RuntimeError("Templates not configured")
    return templates
