from __future__ import annotations

from app.models import GameResult


STOCKFISH_RATING = 3200.0
K_FACTOR = 32.0


def expected_score(player_rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opponent_rating - player_rating) / 400.0))


def result_to_score(result: GameResult) -> float:
    match result:
        case GameResult.WIN:
            return 1.0
        case GameResult.DRAW:
            return 0.5
        case GameResult.LOSS:
            return 0.0
    return 0.5


def adjust_rating(current_rating: float, result: GameResult, opponent_rating: float = STOCKFISH_RATING) -> float:
    expected = expected_score(current_rating, opponent_rating)
    score = result_to_score(result)
    return current_rating + K_FACTOR * (score - expected)
