from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .game import Game


class MoveSide(str, Enum):
    WHITE = "white"
    BLACK = "black"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Move(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    ply: int = Field(index=True)
    side: MoveSide = Field(index=True)
    san: str = Field(max_length=32)
    evaluation: Optional[float] = None
    timestamp: datetime = Field(default_factory=_utcnow, nullable=False, index=True)

    game: "Game" = Relationship(back_populates="moves")
