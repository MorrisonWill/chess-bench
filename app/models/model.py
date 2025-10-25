from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from ._utils import utcnow

if TYPE_CHECKING:
    from .game import Game
    from .schedule import MatchSchedule


class Model(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    openrouter_model: str = Field(index=True)
    rating: float = Field(default=1200.0)
    last_active_at: Optional[datetime] = None
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    games: list["Game"] = Relationship(back_populates="model")
    schedules: list["MatchSchedule"] = Relationship(back_populates="model")
