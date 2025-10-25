from __future__ import annotations

from app.models import GameResult


STOCKFISH_RATING = 3200.0
K_FACTOR = 32.0
RESULT_SCORES = {
    GameResult.WIN: 1.0,
    GameResult.DRAW: 0.5,
    GameResult.LOSS: 0.0,
}


def adjust_rating(current_rating: float, result: GameResult, opponent_rating: float = STOCKFISH_RATING) -> float:
    expected = 1.0 / (1.0 + 10 ** ((opponent_rating - current_rating) / 400.0))
    score = RESULT_SCORES[result]
    return current_rating + K_FACTOR * (score - expected)
