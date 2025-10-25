from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import orchestrator_dependency, session_dependency, templates_dependency
from app.internal.orchestrator import GameOrchestrator
from app.models import MatchSchedule, MatchStatus, Model


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/", response_class=HTMLResponse)
async def admin_home(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
    templates=Depends(templates_dependency),
) -> HTMLResponse:
    models = await _load_models(session)
    schedules = await _load_schedules(session)
    context = {
        "request": request,
        "models": models,
        "schedules": schedules,
    }
    return templates.TemplateResponse("admin/index.html", context)


@router.post("/models")
async def create_model(
    name: str = Form(...),
    openrouter_model: str = Form(...),
    rating: str | None = Form(default=None),
    is_active: bool = Form(default=False),
    session: AsyncSession = Depends(session_dependency),
) -> RedirectResponse:
    model = Model(
        name=name.strip(),
        openrouter_model=openrouter_model.strip(),
        rating=_coerce_rating(rating),
        is_active=is_active,
    )
    session.add(model)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/models/{model_id}/toggle")
async def toggle_model(
    model_id: int,
    session: AsyncSession = Depends(session_dependency),
) -> RedirectResponse:
    model = await session.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_active = not model.is_active
    await session.flush()
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/models/{model_id}/schedule")
async def schedule_model(
    model_id: int,
    session: AsyncSession = Depends(session_dependency),
    orchestrator: GameOrchestrator = Depends(orchestrator_dependency),
) -> RedirectResponse:
    model = await session.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    schedule = MatchSchedule(model=model)
    session.add(schedule)
    await session.flush()
    await session.commit()
    await orchestrator.run_once([model.id])
    return RedirectResponse(url="/admin", status_code=303)


async def _load_models(session: AsyncSession) -> list[Model]:
    result = await session.execute(select(Model).order_by(Model.name))
    return list(result.scalars().unique())


async def _load_schedules(session: AsyncSession) -> list[MatchSchedule]:
    query = (
        select(MatchSchedule)
        .options(selectinload(MatchSchedule.model))
        .where(MatchSchedule.status.in_([MatchStatus.PENDING, MatchStatus.RUNNING]))
        .order_by(MatchSchedule.scheduled_for.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().unique())


def _coerce_rating(raw: str | None) -> float:
    try:
        return float(raw) if raw else 1200.0
    except ValueError:
        return 1200.0
