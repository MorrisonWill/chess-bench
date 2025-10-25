from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

from app.config import get_settings
from app.logging_config import configure_logging
from app.services.game_manager import create_game_manager


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chess Arena CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-games", help="Run games for active models")
    run_parser.add_argument("--model-id", action="append", help="Restrict to specific model id", dest="model_ids")
    run_parser.add_argument("--dry-run", action="store_true", help="Use scripted moves and skip rating updates")
    run_parser.add_argument(
        "--scripted-move",
        action="append",
        dest="scripted_moves",
        help="Provide scripted UCI moves for dry-run scenarios",
    )

    serve_parser = subparsers.add_parser("serve", help="Start the FastAPI web server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser


async def run_games_async(model_ids: Sequence[str] | None, dry_run: bool, scripted_moves: Sequence[str] | None) -> None:
    manager = create_game_manager(dry_run=dry_run, scripted_moves=scripted_moves)
    try:
        await manager.run_games(model_ids=model_ids)
    finally:
        await manager.shutdown()


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    if args.command == "run-games":
        asyncio.run(run_games_async(args.model_ids, args.dry_run, args.scripted_moves))
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("app.main:app", host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
