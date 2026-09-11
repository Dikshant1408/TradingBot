"""
Backtesting API routes.
Features chronological execution, explicit data quality validation, zero silent demo fallbacks,
configurable broker tariff models, and strategy experiment management (Research Mode).
"""
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import BacktestRunModel, ExperimentModel
from app.data.loader import DataLoader
from app.data.providers import MarketDataService
from app.strategies.registry import strategy_registry
from app.backtesting.engine import BacktestEngine
from app.backtesting.reports import BacktestReportGenerator
from app.backtesting.data_validator import DataQualityValidator
from app.config.settings import get_settings

from app.backtesting.execution_models import ExecutionModel
from app.backtesting.walk_forward import WalkForwardAnalyzer
from app.backtesting.monte_carlo import MonteCarloSimulator

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])
settings = get_settings()


class BacktestRequest(BaseModel):
    strategy_id: str = "MA_Crossover"
    symbol: str = "NIFTY50_DEMO"
    initial_capital: float = 100000.0
    position_size_pct: float = 0.50
    brokerage: float = 20.0
    broker_profile: str = "ZERODHA"
    segment: str = "EQUITY_INTRADAY"
    slippage_pct: float = 0.0005
    execution_model: str = "NEXT_OPEN"
    allow_shorting: bool = False
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SaveExperimentRequest(BaseModel):
    name: str
    backtest_id: str
    symbol: str = ""
    strategy_id: str = ""
    hypothesis: Optional[str] = ""
    tags: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = ""
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class WalkForwardRequest(BaseModel):
    strategy_id: str = "MA_Crossover"
    symbol: str = "NIFTY50_DEMO"
    train_bars: int = 100
    test_bars: int = 40
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.post("/run")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    """
    Execute a backtest run on historical data with realistic Indian market execution costs.
    Strictly verifies data quality and never falls back silently to demo data for real instruments.
    """
    # 1. Load data via authoritative MarketDataService (fails fast on network errors for real symbols)
    try:
        df = MarketDataService.get_historical_candles(req.symbol)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Market data retrieval failed for {req.symbol}: {str(e)}"
        )

    if df is None or df.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No candles available for {req.symbol}. Data provider returned empty dataset."
        )

    # 2. Run Data Quality Pre-Flight Audit
    data_quality_report = DataQualityValidator.validate(df, req.symbol)
    if not data_quality_report.is_valid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Data quality pre-flight audit failed for {req.symbol} (Score: {data_quality_report.quality_score}/100): "
                f"{'; '.join(a['message'] for a in data_quality_report.anomalies[:2])}"
            )
        )

    # 3. Instantiate strategy
    try:
        strategy = strategy_registry.create(req.strategy_id, parameters=req.parameters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid strategy configuration: {str(e)}")

    # Parse execution model
    try:
        exec_model = ExecutionModel(req.execution_model)
    except ValueError:
        exec_model = ExecutionModel.NEXT_OPEN

    # 4. Execute backtest with broker tariff model and shorting restrictions
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=req.initial_capital,
        position_size_pct=req.position_size_pct,
        brokerage=req.brokerage,
        segment=req.segment,
        slippage_pct=req.slippage_pct,
        execution_model=exec_model,
        broker_profile=req.broker_profile,
        allow_shorting=req.allow_shorting
    )

    result = engine.run(df, symbol=req.symbol)
    metrics = result["metrics"]
    result["data_quality"] = data_quality_report.model_dump()
    result["is_demo"] = MarketDataService.is_demo_symbol(req.symbol)
    result["broker_profile"] = req.broker_profile

    # 5. Persist run to SQLite
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
            "is_demo": MarketDataService.is_demo_symbol(r.symbol),
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


# -------- Research & Experiment Endpoints --------
# IMPORTANT: These MUST be defined before /{run_id} catch-all route

@router.get("/experiments")
def list_experiments(limit: int = 100, db: Session = Depends(get_db)):
    """Return all saved experiments ordered by most recent first with nested metrics object."""
    exps = db.query(ExperimentModel).order_by(ExperimentModel.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "backtest_id": e.run_id,
            "symbol": e.symbol,
            "strategy_id": e.strategy_name,
            "hypothesis": e.hypothesis,
            "tags": [t.strip() for t in (e.tags or "").split(",") if t.strip()],
            "notes": e.notes,
            "metrics": {
                "return_pct": e.return_pct,
                "net_pnl": e.net_pnl,
                "sharpe_ratio": e.sharpe_ratio,
                "max_drawdown": e.max_drawdown,
                "win_rate": e.win_rate,
                "total_trades": e.total_trades,
                "quality_score": e.quality_score,
            },
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in exps
    ]


@router.post("/experiments")
def save_experiment(req: SaveExperimentRequest, db: Session = Depends(get_db)):
    """Persist a named experiment snapshot linked to a completed backtest run."""
    run = db.query(BacktestRunModel).filter(BacktestRunModel.id == req.backtest_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Backtest run {req.backtest_id} not found.")

    m = req.metrics or {}
    exp = ExperimentModel(
        name=req.name,
        run_id=req.backtest_id,
        strategy_name=req.strategy_id or run.strategy_name,
        symbol=req.symbol or run.symbol,
        hypothesis=req.hypothesis or "",
        tags=", ".join(req.tags) if req.tags else "",
        notes=req.notes or "",
        quality_score=float(m.get("quality_score", 0) or 0),
        return_pct=float(m.get("return_pct", run.return_pct) or 0),
        net_pnl=float(m.get("net_pnl", run.net_pnl) or 0),
        sharpe_ratio=float(m.get("sharpe_ratio", run.sharpe_ratio) or 0),
        max_drawdown=float(m.get("max_drawdown", run.max_drawdown) or 0),
        win_rate=float(m.get("win_rate", run.win_rate) or 0),
        total_trades=int(m.get("total_trades", run.total_trades) or 0),
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return {"id": exp.id, "name": exp.name, "created_at": exp.created_at.isoformat()}


@router.delete("/experiments/{experiment_id}")
def delete_experiment(experiment_id: str, db: Session = Depends(get_db)):
    """Delete a saved experiment by ID."""
    exp = db.query(ExperimentModel).filter(ExperimentModel.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    db.delete(exp)
    db.commit()
    return {"deleted": experiment_id}



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
        "is_demo": MarketDataService.is_demo_symbol(run.symbol),
        "start_date": run.start_date,
        "end_date": run.end_date,
        "metrics": json.loads(run.metrics_json),
        "parameters": json.loads(run.params_json),
        "trades": json.loads(run.trades_json),
        "equity_curve": json.loads(run.equity_curve_json),
        "created_at": run.created_at.isoformat() if run.created_at else None
    }


@router.post("/{run_id}/save-experiment")
def save_backtest_as_experiment(run_id: str, req: SaveExperimentRequest, db: Session = Depends(get_db)):
    """
    Save a backtest run as a named Research Experiment.
    Maintains a laboratory log of hypotheses, parameters, and results.
    """
    run = db.query(BacktestRunModel).filter(BacktestRunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found.")

    metrics = json.loads(run.metrics_json)
    exp = ExperimentModel(
        name=req.name,
        hypothesis=req.hypothesis,
        tags=req.tags,
        notes=req.notes,
        run_id=run.id,
        strategy_name=run.strategy_name,
        symbol=run.symbol,
        return_pct=run.return_pct,
        net_pnl=run.net_pnl,
        sharpe_ratio=run.sharpe_ratio,
        max_drawdown=run.max_drawdown,
        win_rate=run.win_rate,
        total_trades=run.total_trades
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)

    return {
        "status": "SAVED",
        "experiment_id": exp.id,
        "name": exp.name,
        "run_id": exp.run_id,
        "message": f"Experiment '{exp.name}' recorded in Research Log."
    }


@router.get("/compare")
def compare_backtests(run_ids: str = Query(..., description="Comma-separated run IDs to compare"), db: Session = Depends(get_db)):
    """
    Compare multiple backtest executions side-by-side.
    """
    ids = [i.strip() for i in run_ids.split(",") if i.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="No run IDs provided.")

    runs = db.query(BacktestRunModel).filter(BacktestRunModel.id.in_(ids)).all()
    if not runs:
        raise HTTPException(status_code=404, detail="None of the specified runs were found.")

    comparison = []
    for r in runs:
        metrics = json.loads(r.metrics_json)
        params = json.loads(r.params_json)
        comparison.append({
            "id": r.id,
            "strategy_name": r.strategy_name,
            "symbol": r.symbol,
            "is_demo": MarketDataService.is_demo_symbol(r.symbol),
            "parameters": params,
            "metrics": {
                "return_pct": r.return_pct,
                "net_pnl": r.net_pnl,
                "win_rate": r.win_rate,
                "total_trades": r.total_trades,
                "max_drawdown": r.max_drawdown,
                "sharpe_ratio": r.sharpe_ratio,
                "sortino_ratio": r.sortino_ratio,
                "profit_factor": r.profit_factor,
                "total_fees": r.total_fees
            },
            "created_at": r.created_at.isoformat() if r.created_at else None
        })

    return {"count": len(comparison), "runs": comparison}


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


@router.post("/walk-forward")
def run_walk_forward_analysis(req: WalkForwardRequest):
    """
    Run rolling window walk-forward validation (Train vs Test) on historical data.
    """
    df = MarketDataService.get_historical_candles(req.symbol)
    strat_cls = strategy_registry.get(req.strategy_id)
    if not strat_cls:
        raise HTTPException(status_code=404, detail=f"Strategy {req.strategy_id} not found.")

    res = WalkForwardAnalyzer.run_walk_forward(
        df=df,
        symbol=req.symbol,
        strategy_class=strat_cls,
        parameters=req.parameters,
        train_bars=req.train_bars,
        test_bars=req.test_bars
    )
    return res


@router.post("/{run_id}/monte-carlo")
def run_monte_carlo_for_run(run_id: str, simulations: int = 1000, db: Session = Depends(get_db)):
    """
    Re-run Monte Carlo bootstrap simulation on an existing backtest run's trade list.
    """
    run = db.query(BacktestRunModel).filter(BacktestRunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found.")

    trades = json.loads(run.trades_json)
    mc = MonteCarloSimulator.run_simulation(
        trades=trades,
        initial_capital=run.initial_capital,
        simulations=simulations
    )
    return mc


