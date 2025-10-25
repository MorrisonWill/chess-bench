from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from ._utils import utcnow

if TYPE_CHECKING:
    from .game import Game
    from .model import Model


class MatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MatchSchedule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="model.id", index=True)
    scheduled_for: datetime = Field(default_factory=utcnow, index=True)
    status: MatchStatus = Field(default=MatchStatus.PENDING, index=True)
    game_id: Optional[int] = Field(default=None, foreign_key="game.id", index=True)

    model: "Model" = Relationship(back_populates="schedules")
    game: Optional["Game"] = Relationship(
        back_populates="schedule",
        sa_relationship_kwargs={"uselist": False},
    )
