from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .game import Game
    from .schedule import MatchSchedule


class Model(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    openrouter_model: str = Field(index=True)
    rating: float = Field(default=1200.0)
    last_active_at: datetime | None = None
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    games: list["Game"] = Relationship(back_populates="model")
    schedules: list["MatchSchedule"] = Relationship(back_populates="model")
