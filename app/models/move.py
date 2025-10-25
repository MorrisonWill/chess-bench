from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .game import Game


class MoveSide(str, Enum):
    WHITE = "white"
    BLACK = "black"


class Move(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    ply: int = Field(index=True)
    side: MoveSide = Field(index=True)
    san: str = Field(max_length=32)
    evaluation: float | None = None
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, nullable=False, index=True
    )

    game: "Game" = Relationship(back_populates="moves")
