from __future__ import annotations

from pathlib import Path
from typing import Sequence

from sqlalchemy import select

from app.config import Settings, get_settings
from app.database import create_db_and_tables, get_session, get_session_factory
from app.internal.openrouter import OpenRouterClient
from app.internal.orchestrator import GameOrchestrator
from app.internal.stockfish import StockfishEngine
from app.models import MatchSchedule, MatchStatus, Model


class GameManager:
    def __init__(
        self,
        settings: Settings,
        orchestrator: GameOrchestrator,
        stockfish: StockfishEngine | None,
        openrouter: OpenRouterClient | None,
    ) -> None:
        self._settings = settings
        self._orchestrator = orchestrator
        self._stockfish = stockfish
        self._openrouter = openrouter

    async def run_games(self, model_ids: Sequence[str] | None = None) -> None:
        await create_db_and_tables(self._settings)
        await self._ensure_schedules(model_ids)
        await self._orchestrator.start()
        await self._orchestrator.run_once(self._coerce_ids(model_ids))

    async def shutdown(self) -> None:
        await self._orchestrator.stop()

    async def _ensure_schedules(self, model_ids: Sequence[str] | None) -> None:
        ids = self._coerce_ids(model_ids)
        async with get_session(self._settings) as session:
            query = select(Model).where(Model.is_active.is_(True))
            if ids:
                query = query.where(Model.id.in_(ids))
            models = (await session.execute(query)).scalars().all()
            for model in models:
                existing = await session.execute(
                    select(MatchSchedule).where(
                        MatchSchedule.model_id == model.id,
                        MatchSchedule.status == MatchStatus.PENDING,
                    )
                )
                if existing.scalars().first() is None:
                    session.add(MatchSchedule(model_id=model.id))

    @staticmethod
    def _coerce_ids(model_ids: Sequence[str] | None) -> list[int] | None:
        if model_ids is None:
            return None
        coerced: list[int] = []
        for mid in model_ids:
            try:
                coerced.append(int(mid))
            except (TypeError, ValueError):
                continue
        return coerced


def create_game_manager(dry_run: bool = False, scripted_moves: Sequence[str] | None = None) -> GameManager:
    settings = get_settings()
    session_factory = get_session_factory(settings)
    stockfish = None if dry_run else StockfishEngine(settings.stockfish_path)
    openrouter = None if dry_run else OpenRouterClient(str(settings.openrouter_base_url), settings.openrouter_api_key)
    orchestrator = GameOrchestrator(
        session_factory=session_factory,
        stockfish=stockfish,
        openrouter=openrouter,
        scheduler_interval=settings.scheduler_interval_seconds,
        pgn_directory=Path("pgn"),
        dry_run=dry_run,
        scripted_moves=scripted_moves,
    )
    return GameManager(settings, orchestrator, stockfish, openrouter)
