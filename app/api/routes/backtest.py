"""
Backtesting API routes.
"""
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import BacktestRunModel
from app.data.loader import DataLoader
from app.strategies.registry import strategy_registry
from app.backtesting.engine import BacktestEngine
from app.backtesting.reports import BacktestReportGenerator
from app.config.settings import get_settings

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])
settings = get_settings()


class BacktestRequest(BaseModel):
    strategy_id: str = "MA_Crossover"
    symbol: str = "NIFTY50_DEMO"
    initial_capital: float = 100000.0
    position_size_pct: float = 0.50
    brokerage: float = 20.0
    stt_rate: float = 0.00025
    slippage_pct: float = 0.0005
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("/run")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    """
    Execute a backtest run on historical data with realistic Indian market execution costs.
    """
    # 1. Load data
    df = DataLoader.get_processed(req.symbol)
    if df is None:
        sample_path = settings.DATA_DIR / "samples" / f"{req.symbol.upper()}.csv"
        if sample_path.exists():
            df, _ = DataLoader.load_csv(sample_path, req.symbol)
        else:
            # Generate demo data automatically if needed
            sample_path = DataLoader.generate_demo_dataset(req.symbol)
            df, _ = DataLoader.load_csv(sample_path, req.symbol)

    if df.empty:
        raise HTTPException(status_code=400, detail=f"No candles available for {req.symbol}")

    # 2. Instantiate strategy
    try:
        strategy = strategy_registry.create(req.strategy_id, parameters=req.parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid strategy configuration: {str(e)}")

    # 3. Execute backtest
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=req.initial_capital,
        position_size_pct=req.position_size_pct,
        brokerage=req.brokerage,
        stt_rate=req.stt_rate,
        slippage_pct=req.slippage_pct
    )

    result = engine.run(df, symbol=req.symbol)
    metrics = result["metrics"]

    # 4. Persist run to SQLite
    try:
        run_record = BacktestRunModel(
            id=result["id"],
            strategy_name=result["strategy_name"],
            strategy_version=result["strategy_version"],
            symbol=result["symbol"],
            timeframe="1d",
            start_date=result["start_date"],
            end_date=result["end_date"],
            initial_capital=metrics["initial_capital"],
            final_capital=metrics["final_capital"],
            net_pnl=metrics["net_pnl"],
            return_pct=metrics["return_pct"],
            cagr=metrics.get("cagr"),
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            total_fees=metrics["total_fees"],
            slippage_cost=metrics["slippage_cost"],
            params_json=json.dumps(result["parameters"]),
            metrics_json=json.dumps(metrics),
            equity_curve_json=json.dumps(result["equity_curve"]),
            trades_json=json.dumps(result["trades"])
        )
        db.add(run_record)
        db.commit()
    except Exception as e:
        db.rollback()
        # Non-fatal for execution output

    return result


@router.get("/history")
def list_backtests(limit: int = 20, db: Session = Depends(get_db)):
    """List historical backtest executions."""
    runs = db.query(BacktestRunModel).order_by(BacktestRunModel.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "strategy_name": r.strategy_name,
            "symbol": r.symbol,
            "return_pct": r.return_pct,
            "net_pnl": r.net_pnl,
            "win_rate": r.win_rate,
            "max_drawdown": r.max_drawdown,
            "sharpe_ratio": r.sharpe_ratio,
            "total_trades": r.total_trades,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in runs
    ]


@router.get("/{run_id}")
def get_backtest_details(run_id: str, db: Session = Depends(get_db)):
    """Retrieve full details, metrics, and trades for a specific backtest."""
    run = db.query(BacktestRunModel).filter(BacktestRunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found.")

    return {
        "id": run.id,
        "strategy_name": run.strategy_name,
        "strategy_version": run.strategy_version,
        "symbol": run.symbol,
        "start_date": run.start_date,
        "end_date": run.end_date,
        "metrics": json.loads(run.metrics_json),
        "parameters": json.loads(run.params_json),
        "trades": json.loads(run.trades_json),
        "equity_curve": json.loads(run.equity_curve_json),
        "created_at": run.created_at.isoformat() if run.created_at else None
    }


@router.get("/{run_id}/export-csv")
def export_backtest_trades_csv(run_id: str, db: Session = Depends(get_db)):
    """Export completed backtest trades as downloadable CSV."""
    run = db.query(BacktestRunModel).filter(BacktestRunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found.")

    trades = json.loads(run.trades_json)
    csv_content = BacktestReportGenerator.export_trades_csv(trades)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=trades_{run.symbol}_{run_id[:8]}.csv"}
    )
