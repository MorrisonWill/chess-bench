from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Sequence

import chess
import chess.pgn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.internal.openrouter import OpenRouterClient, OpenRouterModelConfig, OpenRouterMoveError
from app.internal.ratings import adjust_rating
from app.internal.stockfish import StockfishEngine
from app.models import Game, GameResult, MatchSchedule, MatchStatus, Model, Move, MoveSide


logger = logging.getLogger(__name__)


class GameOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        stockfish: StockfishEngine | None,
        openrouter: OpenRouterClient | None,
        scheduler_interval: float,
        pgn_directory: Path,
        dry_run: bool = False,
        scripted_moves: Sequence[str] | None = None,
    ) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory
        self._stockfish = stockfish
        self._openrouter = openrouter
        self._scheduler_interval = scheduler_interval
        self._pgn_directory = pgn_directory
        self._dry_run = dry_run
        self._scripted_moves = list(scripted_moves or [])
        self._task: asyncio.Task[None] | None = None
        self._pgn_directory.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        await self._ensure_dependencies_ready()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._openrouter:
            await self._openrouter.close()
        if self._stockfish:
            await self._stockfish.stop()

    async def run_once(self, model_ids: Sequence[int | str] | None = None) -> None:
        await self._ensure_dependencies_ready()
        await self._process_pending_matches(model_ids)

    async def _run_loop(self) -> None:
        try:
            while True:
                await self._process_pending_matches(None)
                await asyncio.sleep(self._scheduler_interval)
        except asyncio.CancelledError:
            raise

    async def _process_pending_matches(self, model_ids: Sequence[int | str] | None) -> None:
        ids = self._normalize_ids(model_ids)
        async with self._session_factory() as session:
            query = select(MatchSchedule).where(MatchSchedule.status == MatchStatus.PENDING)
            if ids:
                query = query.where(MatchSchedule.model_id.in_(ids))
            schedules = (await session.execute(query.order_by(MatchSchedule.scheduled_for))).scalars().all()
        for schedule in schedules:
            await self._run_schedule(schedule.id)

    async def _run_schedule(self, schedule_id: int) -> None:
        async with self._session_factory() as session:
            schedule = await session.get(MatchSchedule, schedule_id)
            if schedule is None:
                return
            if schedule.status != MatchStatus.PENDING:
                return
            model = await session.get(Model, schedule.model_id)
            if model is None or not model.is_active:
                schedule.status = MatchStatus.FAILED
                await session.commit()
                return
            schedule.status = MatchStatus.RUNNING
            game = Game(model_id=model.id)
            session.add(game)
            await session.flush()
            schedule.game_id = game.id
            await session.commit()
            try:
                result = await self._play_game(game.id, model.id)
            except Exception as exc:
                schedule.status = MatchStatus.FAILED
                await session.commit()
                logger.exception("Match %s failed", schedule.id, exc_info=exc)
                return
            schedule.status = MatchStatus.COMPLETED
            await session.commit()

    async def _play_game(self, game_id: int, model_id: int) -> GameResult | None:
        async with self._session_factory() as session:
            game = await session.get(Game, game_id)
            model = await session.get(Model, model_id)
            if game is None or model is None:
                return None
            board = chess.Board()
            san_history: list[str] = []
            pgn_game = chess.pgn.Game()
            timestamp = datetime.utcnow()
            pgn_game.headers.update(
                {
                    "Event": "Chessbench Daily Match",
                    "Date": timestamp.strftime("%Y.%m.%d"),
                    "White": model.name,
                    "Black": "Stockfish",
                }
            )
            node = pgn_game
            moves_played = 0
            max_half_moves = 400

            while not board.is_game_over(claim_draw=True) and moves_played < max_half_moves:
                model_turn = board.turn == chess.WHITE
                move, san = await self._choose_move(board, san_history, model_turn=model_turn, model=model)
                node = node.add_variation(move)
                san_history.append(san)
                side = MoveSide.WHITE if model_turn else MoveSide.BLACK
                session.add(Move(game_id=game.id, ply=moves_played + 1, side=side, san=san))
                board.push(move)
                moves_played += 1

            board_result = board.result(claim_draw=True)
            result = self._map_result(board_result)
            game.completed_at = datetime.utcnow()
            game.moves_count = moves_played
            game.result = result
            game.opening = " ".join(san_history[:6]) or None
            pgn_game.headers["Result"] = self._pgn_result_string(result)
            pgn_path = self._write_pgn(pgn_game, game.id)
            game.pgn_path = str(pgn_path)
            model.last_active_at = datetime.utcnow()
            if not self._dry_run:
                model.rating = adjust_rating(model.rating, result)
            await session.commit()
            return result

    async def _choose_move(
        self,
        board: chess.Board,
        san_history: Sequence[str],
        *,
        model_turn: bool,
        model: Model,
    ) -> tuple[chess.Move, str]:
        scripted = self._next_scripted_move(board)
        if scripted is not None:
            return scripted, board.san(scripted)
        if model_turn and not self._dry_run and self._openrouter is not None:
            config = OpenRouterModelConfig(name=model.openrouter_model)
            san = await self._openrouter.get_move(board.fen(), san_history, config)
            try:
                move = board.parse_san(san)
            except ValueError as exc:
                raise OpenRouterMoveError(f"Invalid SAN provided by model: {san}") from exc
            return move, san
        if not model_turn and not self._dry_run and self._stockfish is not None:
            move = await self._stockfish.choose_move(board)
            return move, board.san(move)
        move = self._fallback_move(board)
        return move, board.san(move)

    def _next_scripted_move(self, board: chess.Board) -> chess.Move | None:
        if not self._scripted_moves:
            return None
        raw = self._scripted_moves.pop(0)
        try:
            move = chess.Move.from_uci(raw)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        return move

    @staticmethod
    def _fallback_move(board: chess.Board) -> chess.Move:
        return next(iter(board.legal_moves))

    def _write_pgn(self, game: chess.pgn.Game, game_id: int) -> Path:
        path = self._pgn_directory / f"game_{game_id}.pgn"
        path.write_text(str(game), encoding="utf-8")
        return path

    async def _ensure_dependencies_ready(self) -> None:
        if self._stockfish:
            await self._stockfish.start()
        if self._openrouter:
            await self._openrouter.start()

    @staticmethod
    def _map_result(result_string: str) -> GameResult:
        return {
            "1-0": GameResult.WIN,
            "0-1": GameResult.LOSS,
        }.get(result_string, GameResult.DRAW)

    @staticmethod
    def _pgn_result_string(result: GameResult) -> str:
        return {
            GameResult.WIN: "1-0",
            GameResult.LOSS: "0-1",
            GameResult.DRAW: "1/2-1/2",
        }[result]

    @staticmethod
    def _normalize_ids(model_ids: Sequence[int | str] | None) -> set[int]:
        if not model_ids:
            return set()
        normalized: set[int] = set()
        for item in model_ids:
            if isinstance(item, int):
                normalized.add(item)
            elif isinstance(item, str) and item.isdigit():
                normalized.add(int(item))
        return normalized
