"""Friction — AI Deliberation Server.

FastAPI application with deliberation engine, ticket orchestration,
and MCP-compatible agent interface. Deployed on Vercel with Fluid Compute.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.codebase.analyzer import CodebaseAnalyzer
from backend.codebase.github_issues import GitHubIssuesFetcher
from backend.codebase.importer import CodebaseImporter
from backend.codebase.issue_ticket_generator import IssueTicketGenerator
from backend.config import config
from backend.deliberation.engine import DeliberationEngine
from backend.routers import codebase as codebase_router
from backend.routers import sessions as sessions_router
from backend.routers import status as status_router
from backend.routers import tickets as tickets_router
from backend.routers import workflow as workflow_router
from backend.services.db import init_db
from backend.services.llm import LLMClient
from backend.services.websocket_manager import ConnectionManager
from backend.tickets.generator import TicketGenerator
from backend.tickets.manager import TicketManager

_IS_VERCEL = bool(os.environ.get("VERCEL"))

# Resolve frontend dist path relative to this file (local dev only)
_THIS_DIR = Path(__file__).resolve().parent
_FRONTEND_DIST = _THIS_DIR.parent / "frontend" / "dist"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Friction server...")
    await init_db()

    llm = LLMClient()
    app.state.llm = llm
    app.state.engine = DeliberationEngine(llm)
    app.state.generator = TicketGenerator(llm)
    app.state.manager = TicketManager(llm)
    app.state.ws_manager = ConnectionManager()
    app.state.importer = CodebaseImporter()
    app.state.analyzer = CodebaseAnalyzer(llm)
    app.state.issues_fetcher = GitHubIssuesFetcher()
    app.state.issue_ticket_generator = IssueTicketGenerator(llm)

    logger.info("Friction server ready")
    yield
    # Shutdown
    logger.info("Friction server shutting down.")


app = FastAPI(
    title="Friction - AI Deliberation Server",
    description="The AI that debates your idea, then builds the plan that survives the debate.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins for deployed API
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(sessions_router.router)
app.include_router(tickets_router.router)
app.include_router(workflow_router.router)
app.include_router(codebase_router.router)
app.include_router(status_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "friction", "vercel": _IS_VERCEL}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ws_manager: ConnectionManager = app.state.ws_manager
    client_id = str(uuid4())
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


# ---------------------------------------------------------------------------
# Local dev: Serve built frontend (Vercel serves from public/ automatically)
# ---------------------------------------------------------------------------
if not _IS_VERCEL:
    if _FRONTEND_DIST.is_dir() and (_FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(request: Request, full_path: str):
        """Serve frontend files. API routes are matched first by FastAPI."""
        if not _FRONTEND_DIST.is_dir():
            return JSONResponse(
                {"detail": "Frontend not built. Run: cd frontend && npm run build"},
                status_code=404,
            )
        if full_path:
            file_path = _FRONTEND_DIST / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
        index = _FRONTEND_DIST / "index.html"
        if index.is_file():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Not found"}, status_code=404)
