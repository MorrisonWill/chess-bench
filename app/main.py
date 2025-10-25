from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import create_db_and_tables, get_session_factory
from app.internal.openrouter import OpenRouterClient
from app.internal.orchestrator import GameOrchestrator
from app.internal.stockfish import StockfishEngine
from app.routers import dashboard, games, models


BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await create_db_and_tables(settings)
    session_factory = get_session_factory(settings)
    stockfish = None if settings.test_mode else StockfishEngine(settings.stockfish_path)
    openrouter = None if settings.test_mode else OpenRouterClient(str(settings.openrouter_base_url), settings.openrouter_api_key)
    orchestrator = GameOrchestrator(
        session_factory=session_factory,
        stockfish=stockfish,
        openrouter=openrouter,
        scheduler_interval=settings.scheduler_interval_seconds,
        pgn_directory=BASE_DIR.parent / "pgn",
        dry_run=settings.test_mode,
    )
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.state.settings = settings
    app.state.templates = templates
    app.state.orchestrator = orchestrator
    await orchestrator.start()
    try:
        yield
    finally:
        await orchestrator.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(dashboard.router)
app.include_router(games.router, prefix="/api")
app.include_router(models.router, prefix="/api")

static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/healthz")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
