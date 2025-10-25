from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

import chess
import chess.engine


class StockfishUnavailableError(RuntimeError):
    """Raised when the Stockfish binary cannot be located."""


class StockfishEngine:
    def __init__(self, binary_path: str, default_time: float = 0.5, skill_level: int = 20) -> None:
        self._binary_path = binary_path
        self._default_limit = chess.engine.Limit(time=default_time)
        self._skill_level = skill_level
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._engine is not None

    async def start(self) -> None:
        if self._engine is not None:
            return
        binary = self._resolve_binary()
        engine = await asyncio.to_thread(chess.engine.SimpleEngine.popen_uci, binary)
        await asyncio.to_thread(engine.configure, {"Skill Level": self._skill_level})
        self._engine = engine

    async def stop(self) -> None:
        if self._engine is None:
            return
        engine = self._engine
        self._engine = None
        await asyncio.to_thread(engine.quit)

    async def choose_move(
        self,
        board: chess.Board,
        limit: Optional[chess.engine.Limit] = None,
    ) -> chess.Move:
        if self._engine is None:
            raise RuntimeError("Stockfish engine not started")
        async with self._lock:
            result = await asyncio.to_thread(self._engine.play, board, limit or self._default_limit)
        return result.move

    async def validate(self) -> None:
        self._resolve_binary()

    def _resolve_binary(self) -> str:
        path = Path(self._binary_path)
        if path.is_file():
            return str(path)
        which = shutil.which(self._binary_path)
        if which:
            return which
        raise StockfishUnavailableError(f"Stockfish binary not found at '{self._binary_path}'")
