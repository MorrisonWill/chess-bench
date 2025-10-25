from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.database import get_session, get_session_factory
from app.internal.orchestrator import GameOrchestrator
from app.models import Game, MatchSchedule, Model


@pytest.mark.anyio("asyncio")
async def test_orchestrator_creates_game_in_dry_run(test_settings, tmp_path: Path) -> None:
    session_factory = get_session_factory(test_settings)
    async with get_session(test_settings) as session:
        model = Model(name="Test Model", openrouter_model="test")
        session.add(model)
        await session.flush()
        session.add(MatchSchedule(model_id=model.id))
        model_id = model.id

    pgn_dir = tmp_path / "pgn"
    orchestrator = GameOrchestrator(
        session_factory=session_factory,
        stockfish=None,
        openrouter=None,
        scheduler_interval=0.1,
        pgn_directory=pgn_dir,
        dry_run=True,
        scripted_moves=[
            "e2e4",
            "e7e5",
            "g1f3",
            "b8c6",
            "f1c4",
            "g8f6",
        ],
    )

    await orchestrator.run_once([model_id])
    await orchestrator.stop()

    async with get_session(test_settings) as session:
        games = (await session.execute(select(Game))).scalars().all()
        assert games, "Expected at least one game to be created"
        assert games[0].result is not None

    assert list(pgn_dir.glob("game_*.pgn")), "PGN file should be generated"
