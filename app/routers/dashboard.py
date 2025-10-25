from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import session_dependency, templates_dependency
from app.models import Game, Model


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
    templates: Jinja2Templates = Depends(templates_dependency),
) -> HTMLResponse:
    context = {"request": request, **await _build_dashboard_context(session)}
    settings = getattr(request.app.state, "settings", None)
    context["refresh_seconds"] = getattr(settings, "dashboard_refresh_seconds", 10) if settings else 10
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/partials/active-boards", response_class=HTMLResponse)
async def active_boards_partial(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
    templates: Jinja2Templates = Depends(templates_dependency),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/active_boards.html",
        {"request": request, "active_games": await _active_games(session)},
    )


@router.get("/partials/completed-games", response_class=HTMLResponse)
async def completed_games_partial(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
    templates: Jinja2Templates = Depends(templates_dependency),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/completed_games.html",
        {"request": request, "completed_games": await _completed_games(session)},
    )


@router.get("/partials/rating-table", response_class=HTMLResponse)
async def rating_table_partial(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
    templates: Jinja2Templates = Depends(templates_dependency),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/rating_table.html",
        {
            "request": request,
            "models": await _rating_table(session),
            "generated_at": datetime.utcnow(),
        },
    )


async def _build_dashboard_context(session: AsyncSession) -> dict[str, object]:
    return {
        "active_games": await _active_games(session),
        "completed_games": await _completed_games(session),
        "models": await _rating_table(session),
    }


async def _active_games(session: AsyncSession) -> list[Game]:
    query = (
        select(Game)
        .options(selectinload(Game.model))
        .where(Game.completed_at.is_(None))
        .order_by(Game.started_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().unique())


async def _completed_games(session: AsyncSession) -> list[Game]:
    query = (
        select(Game)
        .options(selectinload(Game.model))
        .where(Game.completed_at.is_not(None))
        .order_by(Game.completed_at.desc())
        .limit(10)
    )
    result = await session.execute(query)
    return list(result.scalars().unique())


async def _rating_table(session: AsyncSession) -> list[Model]:
    query = select(Model).order_by(Model.rating.desc())
    result = await session.execute(query)
    return list(result.scalars().unique())
