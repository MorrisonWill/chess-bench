from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .game import Game
    from .schedule import MatchSchedule


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Model(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    openrouter_model: str = Field(index=True)
    rating: float = Field(default=1200.0)
    last_active_at: Optional[datetime] = None
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)

    games: List["Game"] = Relationship(back_populates="model")
    schedules: List["MatchSchedule"] = Relationship(back_populates="model")
