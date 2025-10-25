from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class MatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MatchSchedule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="model.id", index=True)
    scheduled_for: datetime = Field(default_factory=datetime.utcnow, index=True)
    status: MatchStatus = Field(default=MatchStatus.PENDING, index=True)
    game_id: int | None = Field(default=None, foreign_key="game.id", index=True)

    model: "Model" = Relationship(back_populates="schedules")
    game: "Game" | None = Relationship(back_populates="schedule")
