from __future__ import annotations

from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship, SQLModel

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
    id: int | None = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="model.id", index=True)
    opponent: GameOpponent = Field(default=GameOpponent.STOCKFISH, index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    completed_at: datetime | None = None
    result: GameResult | None = Field(default=None, index=True)
    pgn_path: str | None = None
    opening: str | None = Field(default=None, index=True)
    moves_count: int = Field(default=0)

    model: Model = Relationship(back_populates="games")
    moves: list[Move] = Relationship(back_populates="game")
    schedule: MatchSchedule | None = Relationship(
        back_populates="game",
        sa_relationship_kwargs={"uselist": False},
    )
