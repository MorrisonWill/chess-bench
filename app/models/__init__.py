from .game import Game, GameOpponent, GameResult
from .model import Model
from .move import Move, MoveSide
from .schedule import MatchSchedule, MatchStatus

# Populate module globals so SQLModel forward refs resolve cleanly at runtime.
from . import game as _game_module
from . import model as _model_module
from . import move as _move_module
from . import schedule as _schedule_module

_model_module.Game = Game
_schedule_module.Game = Game
_schedule_module.Model = Model
_move_module.Game = Game

__all__ = [
    "Game",
    "GameOpponent",
    "GameResult",
    "MatchSchedule",
    "MatchStatus",
    "Model",
    "Move",
    "MoveSide",
]
