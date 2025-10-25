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
from sqlalchemy.ext.asyncio import AsyncSession

from app.internal.openrouter import OpenRouterClient, OpenRouterModelConfig, OpenRouterMoveError
from app.internal.ratings import adjust_rating
from app.internal.stockfish import StockfishEngine
from app.models import Game, GameResult, MatchSchedule, MatchStatus, Model, Move, MoveSide


logger = logging.getLogger(__name__)


class GameOrchestrator:
    def __init__(
        self,
        session_factory,
        stockfish: StockfishEngine | None,
        openrouter: OpenRouterClient | None,
        scheduler_interval: float,
        pgn_directory: Path,
        dry_run: bool = False,
        scripted_moves: Sequence[str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._stockfish = stockfish
        self._openrouter = openrouter
        self._scheduler_interval = scheduler_interval
        self._pgn_directory = pgn_directory
        self._dry_run = dry_run
        self._scripted_moves = list(scripted_moves or [])
        self._task: asyncio.Task[None] | None = None
        self._running = asyncio.Event()
        self._pgn_directory.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self._running.is_set():
            return
        await self._ensure_dependencies_ready()
        self._running.set()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        if self._task:
            with suppress(asyncio.CancelledError):
                self._task.cancel()
                await self._task
            self._task = None
        if self._openrouter:
            await self._openrouter.close()
        if self._stockfish:
            await self._stockfish.stop()

    async def run_once(self, model_ids: Sequence[int] | None = None) -> None:
        await self._ensure_dependencies_ready()
        await self._process_pending_matches(model_ids)

    async def _run_loop(self) -> None:
        try:
            while self._running.is_set():
                await self._process_pending_matches(None)
                await asyncio.sleep(self._scheduler_interval)
        except asyncio.CancelledError:
            raise

    async def _process_pending_matches(self, model_ids: Sequence[int] | None) -> None:
        ids: set[int] | None = None
        if model_ids is not None:
            converted: set[int] = set()
            for mid in model_ids:
                try:
                    converted.add(int(mid))
                except (TypeError, ValueError):
                    continue
            ids = converted
        async with self._session_factory() as session:  # type: ignore[call-arg]
            query = select(MatchSchedule).where(MatchSchedule.status == MatchStatus.PENDING)
            if ids:
                query = query.where(MatchSchedule.model_id.in_(ids))
            query = query.order_by(MatchSchedule.scheduled_for)
            schedules = (await session.execute(query)).scalars().all()
        for schedule in schedules:
            await self._run_schedule(schedule.id)

    async def _run_schedule(self, schedule_id: int) -> None:
        async with self._session_factory() as session:  # type: ignore[call-arg]
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
                result = await self._play_game(session, game, model)
            except Exception as exc:
                schedule.status = MatchStatus.FAILED
                await session.commit()
                logger.exception("Match %s failed", schedule.id, exc_info=exc)
                return
            game = await session.get(Game, game.id)
            if game is None:
                return
            schedule = await session.get(MatchSchedule, schedule.id)
            if schedule is None:
                return
            schedule.status = MatchStatus.COMPLETED
            await session.commit()
            if not self._dry_run and result:
                async with self._session_factory() as update_session:  # type: ignore[call-arg]
                    db_model = await update_session.get(Model, model.id)
                    db_game = await update_session.get(Game, game.id)
                    if db_model and db_game and db_game.result:
                        db_model.rating = adjust_rating(db_model.rating, db_game.result)
                        db_model.last_active_at = datetime.utcnow()
                        await update_session.commit()

    async def _play_game(self, session: AsyncSession, game: Game, model: Model) -> GameResult | None:
        model_is_white = True
        board = chess.Board()
        san_history: list[str] = []
        recorded_moves: list[chess.Move] = []
        pgn_game = chess.pgn.Game()
        pgn_game.headers["Event"] = "Chessbench Daily Match"
        pgn_game.headers["Date"] = datetime.utcnow().strftime("%Y.%m.%d")
        pgn_game.headers["White"] = model.name if model_is_white else "Stockfish"
        pgn_game.headers["Black"] = "Stockfish" if model_is_white else model.name
        node = pgn_game
        ply = 1
        max_half_moves = 400

        while not board.is_game_over(claim_draw=True) and ply <= max_half_moves:
            if board.turn == chess.WHITE and model_is_white:
                move, san = await self._choose_model_move(board, san_history, model)
                if move is None:
                    raise OpenRouterMoveError("Model failed to produce a legal move")
            else:
                move, san = await self._choose_stockfish_move(board)
                if move is None:
                    break
            recorded_moves.append(move)
            node = node.add_variation(move)
            san_history.append(san)
            side = MoveSide.WHITE if board.turn == chess.WHITE else MoveSide.BLACK
            board.push(move)
            db_move = Move(game_id=game.id, ply=ply, side=side, san=san)
            session.add(db_move)
            await session.flush()
            await session.commit()
            ply += 1

        board_result = board.result(claim_draw=True)
        result = self._map_result(board_result, model_is_white)
        update_game = await session.get(Game, game.id)
        if update_game is None:
            return None
        update_game.completed_at = datetime.utcnow()
        update_game.moves_count = len(recorded_moves)
        update_game.result = result
        update_game.opening = " ".join(san_history[:6]) if san_history else None
        pgn_game.headers["Result"] = self._pgn_result_string(result)
        pgn_path = self._write_pgn(pgn_game, update_game.id)
        update_game.pgn_path = str(pgn_path)
        model.last_active_at = datetime.utcnow()
        await session.commit()
        return result

    async def _choose_model_move(
        self,
        board: chess.Board,
        san_history: Sequence[str],
        model: Model,
    ) -> tuple[chess.Move | None, str]:
        scripted = self._next_scripted_move(board)
        if scripted is not None:
            san = board.san(scripted)
            return scripted, san
        if self._dry_run or self._openrouter is None:
            move = self._fallback_move(board)
            return move, board.san(move)
        config = OpenRouterModelConfig(name=model.openrouter_model)
        san = await self._openrouter.get_move(board.fen(), san_history, config)
        try:
            move = board.parse_san(san)
        except ValueError as exc:
            raise OpenRouterMoveError(f"Invalid SAN provided by model: {san}") from exc
        return move, san

    async def _choose_stockfish_move(self, board: chess.Board) -> tuple[chess.Move | None, str]:
        scripted = self._next_scripted_move(board)
        if scripted is not None:
            san = board.san(scripted)
            return scripted, san
        if self._dry_run or self._stockfish is None:
            move = self._fallback_move(board)
            return move, board.san(move)
        move = await self._stockfish.choose_move(board)
        san = board.san(move)
        return move, san

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
    def _map_result(result_string: str, model_is_white: bool) -> GameResult:
        if result_string == "1-0":
            return GameResult.WIN if model_is_white else GameResult.LOSS
        if result_string == "0-1":
            return GameResult.LOSS if model_is_white else GameResult.WIN
        return GameResult.DRAW

    @staticmethod
    def _pgn_result_string(result: GameResult) -> str:
        return {
            GameResult.WIN: "1-0",
            GameResult.LOSS: "0-1",
            GameResult.DRAW: "1/2-1/2",
        }[result]
