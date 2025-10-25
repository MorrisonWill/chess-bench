from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import orchestrator_dependency, session_dependency
from app.internal.orchestrator import GameOrchestrator
from app.models import MatchSchedule, MatchStatus, Model


router = APIRouter(tags=["models"])


class ModelCreate(BaseModel):
    name: str
    openrouter_model: str
    rating: float | None = None
    is_active: bool = True


class ModelUpdate(BaseModel):
    name: str | None = None
    openrouter_model: str | None = None
    rating: float | None = None
    is_active: bool | None = None


@router.get("/models")
async def list_models(session: AsyncSession = Depends(session_dependency)) -> list[dict[str, object]]:
    result = await session.execute(select(Model).order_by(Model.name))
    models = result.scalars().unique().all()
    return [_serialize_model(model) for model in models]


@router.post("/models", status_code=201)
async def create_model(payload: ModelCreate, session: AsyncSession = Depends(session_dependency)) -> dict[str, object]:
    model = Model(
        name=payload.name,
        openrouter_model=payload.openrouter_model,
        rating=payload.rating or 1200.0,
        is_active=payload.is_active,
    )
    session.add(model)
    await session.flush()
    return _serialize_model(model)


@router.patch("/models/{model_id}")
async def update_model(
    model_id: int,
    payload: ModelUpdate,
    session: AsyncSession = Depends(session_dependency),
) -> dict[str, object]:
    model = await session.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await session.flush()
    return _serialize_model(model)


@router.post("/models/{model_id}/toggle")
async def toggle_model(
    model_id: int,
    session: AsyncSession = Depends(session_dependency),
) -> dict[str, object]:
    model = await session.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_active = not model.is_active
    await session.flush()
    return _serialize_model(model)


@router.post("/models/{model_id}/schedule")
async def schedule_match(
    model_id: int,
    session: AsyncSession = Depends(session_dependency),
    orchestrator: GameOrchestrator = Depends(orchestrator_dependency),
) -> dict[str, object]:
    model = await session.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    schedule = MatchSchedule(model=model, scheduled_for=datetime.utcnow())
    session.add(schedule)
    await session.flush()
    await session.commit()
    await orchestrator.run_once([model.id])
    return {"status": "scheduled", "schedule_id": schedule.id}


def _serialize_model(model: Model) -> dict[str, object]:
    return {
        "id": model.id,
        "name": model.name,
        "openrouter_model": model.openrouter_model,
        "rating": model.rating,
        "last_active_at": model.last_active_at,
        "is_active": model.is_active,
    }
