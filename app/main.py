"""
FastAPI Application Entry Point.
Initializes database, logging, market data demo sets, routers, and serves the Quant Terminal UI.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config.settings import get_settings
from app.config.logging_config import setup_logging
from app.database.database import init_db
from app.data.loader import initialize_demo_data
from app.api import (
    market_router,
    backtest_router,
    paper_router,
    live_router,
    strategy_router,
    risk_router,
    system_router,
    ws_manager
)
from app.api.websocket import setup_websocket_event_forwarding

settings = get_settings()
logger = setup_logging(settings.LOGS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and graceful shutdown lifecycle.
    """
    logger.info("Initializing QuantDesk India trading application...")
    # 1. Initialize SQLite Database Schema
    init_db()
    # 2. Ensure initial labeled demo datasets exist
    initialize_demo_data()
    # 3. Setup event forwarding to WebSocket clients
    setup_websocket_event_forwarding()
    logger.info(f"QuantDesk India initialized successfully. Mode: {settings.APP_MODE.upper()}")

    yield

    logger.info("Shutting down trading application...")
    from app.paper.engine import paper_engine
    if paper_engine.is_running:
        paper_engine.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Private Personal Quantitative Trading Bot for Indian Markets (NSE/BSE)",
    lifespan=lifespan
)

# CORS restricted to localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(market_router)
app.include_router(backtest_router)
app.include_router(paper_router)
app.include_router(live_router)
app.include_router(strategy_router)
app.include_router(risk_router)
app.include_router(system_router)


# WebSocket endpoint for real-time telemetry
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive ping from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Mount Static Frontend Files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
frontend_dir.mkdir(parents=True, exist_ok=True)
(frontend_dir / "css").mkdir(parents=True, exist_ok=True)
(frontend_dir / "js").mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def serve_index():
    """Serve the single-page Quant Terminal UI."""
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "message": f"QuantDesk India backend active. Mode: {settings.APP_MODE.upper()}",
        "docs": "/docs",
        "api": "/api/system/health"
    }
