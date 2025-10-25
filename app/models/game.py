from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Text
from sqlmodel import Field, Relationship, SQLModel

from ._utils import utcnow

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


class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="model.id", index=True)
    opponent: GameOpponent = Field(default=GameOpponent.STOCKFISH, index=True)
    started_at: datetime = Field(default_factory=utcnow, nullable=False)
    completed_at: Optional[datetime] = None
    result: Optional[GameResult] = Field(default=None, index=True)
    pgn: Optional[str] = Field(default=None, sa_type=Text)
    pgn_path: Optional[str] = None  # Deprecated: retained for existing rows
    moves_count: int = Field(default=0)

    model: "Model" = Relationship(back_populates="games")
    moves: list["Move"] = Relationship(
        back_populates="game",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    schedule: Optional["MatchSchedule"] = Relationship(
        back_populates="game",
        sa_relationship_kwargs={"uselist": False},
    )
