"""
Paper Trading API routes.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.paper.engine import paper_engine
from app.data.loader import DataLoader
from app.strategies.registry import strategy_registry
from app.core.state import state_manager
from app.config.settings import get_settings

router = APIRouter(prefix="/api/paper", tags=["Paper Trading"])
settings = get_settings()


class ConfigurePaperRequest(BaseModel):
    strategy_id: str = "MA_Crossover"
    symbol: str = "NIFTY50_DEMO"
    initial_capital: float = 100000.0
    replay_delay_seconds: float = 0.5
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def get_paper_status():
    """Retrieve full paper trading state, virtual account, and bot status."""
    acc = paper_engine.broker.get_account()
    state = state_manager.state
    return {
        "bot_state": state.model_dump(),
        "account": acc,
        "is_running": paper_engine.is_running,
        "current_bar": paper_engine.current_bar_index,
        "total_bars": len(paper_engine.dataset) if paper_engine.dataset is not None else 0,
        "active_symbol": paper_engine.symbol,
        "active_strategy": paper_engine.strategy.name if paper_engine.strategy else None
    }


@router.post("/configure")
def configure_paper_trading(req: ConfigurePaperRequest):
    """Configure paper trading session parameters."""
    df = DataLoader.get_processed(req.symbol)
    if df is None:
        sample_path = settings.DATA_DIR / "samples" / f"{req.symbol.upper()}.csv"
        if sample_path.exists():
            df, _ = DataLoader.load_csv(sample_path, req.symbol)
        else:
            sample_path = DataLoader.generate_demo_dataset(req.symbol)
            df, _ = DataLoader.load_csv(sample_path, req.symbol)

    if df.empty:
        raise HTTPException(status_code=400, detail=f"No candles available for {req.symbol}")

    try:
        strategy = strategy_registry.create(req.strategy_id, parameters=req.parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid strategy configuration: {str(e)}")

    paper_engine.configure(
        strategy=strategy,
        symbol=req.symbol,
        dataset=df,
        initial_capital=req.initial_capital,
        replay_delay_seconds=req.replay_delay_seconds
    )

    return {
        "message": f"Paper trading configured for {req.symbol} with {req.strategy_id}",
        "initial_capital": req.initial_capital,
        "candles_loaded": len(df)
    }


@router.post("/start")
def start_paper_trading():
    """Start paper trading processing loop."""
    try:
        paper_engine.start()
        return {"status": "RUNNING", "message": "Paper trading started."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pause")
def pause_paper_trading():
    """Pause paper trading processing loop."""
    paper_engine.pause()
    return {"status": "PAUSED", "message": "Paper trading paused."}


@router.post("/stop")
def stop_paper_trading():
    """Stop paper trading session."""
    paper_engine.stop()
    return {"status": "IDLE", "message": "Paper trading stopped."}


@router.post("/step")
def step_paper_trading():
    """Process a single bar forward in replay mode."""
    if paper_engine.dataset is None or paper_engine.current_bar_index >= len(paper_engine.dataset):
        raise HTTPException(status_code=400, detail="No more candles available to process.")

    candle = paper_engine.dataset.iloc[paper_engine.current_bar_index]
    history = paper_engine.dataset.iloc[:paper_engine.current_bar_index + 1]

    result = paper_engine.process_candle(candle, history)
    paper_engine.current_bar_index += 1

    return {
        "bar_index": paper_engine.current_bar_index,
        "candle": {
            "timestamp": str(candle["timestamp"]),
            "close": float(candle["close"])
        },
        "signals_generated": len(result["signals"]),
        "orders_executed": len(result["executed_orders"]),
        "account": result["account"]
    }


@router.get("/positions")
def get_paper_positions():
    """Get open simulated positions."""
    return paper_engine.broker.get_positions()


@router.get("/orders")
def get_paper_orders():
    """Get simulated order book."""
    return paper_engine.broker.get_orders()


@router.get("/trades")
def get_paper_trades():
    """Get closed simulated trades log."""
    return paper_engine.broker.trades
