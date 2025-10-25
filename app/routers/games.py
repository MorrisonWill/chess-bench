from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.dependencies import orchestrator_dependency, session_dependency
from app.internal.orchestrator import GameOrchestrator
from app.models import Game


router = APIRouter(tags=["games"])


@router.get("/games")
async def list_games(
    session: AsyncSession = Depends(session_dependency),
) -> list[dict[str, object]]:
    query = select(Game).order_by(col(Game.started_at).desc()).limit(50)
    result = await session.execute(query)
    games = result.scalars().unique().all()
    return [_serialize_game(game) for game in games]


@router.get("/games/{game_id}")
async def get_game(
    game_id: int, session: AsyncSession = Depends(session_dependency)
) -> dict[str, object]:
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _serialize_game(game)


@router.get("/games/{game_id}/pgn")
async def download_pgn(
    game_id: int, session: AsyncSession = Depends(session_dependency)
) -> Response:
    game = await session.get(Game, game_id)
    if game is None or not game.pgn:
        raise HTTPException(status_code=404, detail="PGN not available")
    filename = f"game_{game_id}.pgn"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(
        content=game.pgn,
        media_type="application/x-chess-pgn",
        headers=headers,
    )


@router.post("/games/resync")
async def resync_games(
    orchestrator: GameOrchestrator = Depends(orchestrator_dependency),
) -> dict[str, str]:
    await orchestrator.run_once(None)
    return {"status": "ok"}


def _serialize_game(game: Game) -> dict[str, object]:
    return {
        "id": game.id,
        "model_id": game.model_id,
        "opponent": game.opponent.value if game.opponent else None,
        "started_at": game.started_at,
        "completed_at": game.completed_at,
        "result": game.result.value if game.result else None,
        "pgn": game.pgn,
        "moves_count": game.moves_count,
    }
