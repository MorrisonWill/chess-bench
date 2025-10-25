from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .model import Model
    from .move import Move
    from .schedule import MatchSchedule


class GameOpponent(str, Enum):
    STOCKFISH = "stockfish"


class GameResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="model.id", index=True)
    opponent: GameOpponent = Field(default=GameOpponent.STOCKFISH, index=True)
    started_at: datetime = Field(default_factory=_utcnow, nullable=False)
    completed_at: Optional[datetime] = None
    result: Optional[GameResult] = Field(default=None, index=True)
    pgn_path: Optional[str] = None
    opening: Optional[str] = Field(default=None, index=True)
    moves_count: int = Field(default=0)

    model: "Model" = Relationship(back_populates="games")
    moves: List["Move"] = Relationship(back_populates="game")
    schedule: Optional["MatchSchedule"] = Relationship(
        back_populates="game",
        sa_relationship_kwargs={"uselist": False},
    )
