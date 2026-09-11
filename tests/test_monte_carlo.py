import pytest
from app.backtesting.monte_carlo import MonteCarloSimulator


def test_monte_carlo_empty_trades():
    sim = MonteCarloSimulator(trades=[], initial_capital=100000.0)
    res = sim.simulate(num_simulations=100)
    assert res["simulations_count"] == 100
    assert res["median_return_pct"] == 0.0
    assert res["risk_of_ruin_pct"] == 0.0


def test_monte_carlo_resampling_distribution():
    # 20 sample trades
    trades = [
        {"net_pnl": 1200.0},
        {"net_pnl": -800.0},
        {"net_pnl": 2400.0},
        {"net_pnl": -600.0},
        {"net_pnl": 1500.0},
        {"net_pnl": -900.0},
        {"net_pnl": 3000.0},
        {"net_pnl": -1200.0},
        {"net_pnl": 500.0},
        {"net_pnl": -400.0}
    ] * 2  # 20 trades

    sim = MonteCarloSimulator(trades=trades, initial_capital=100000.0)
    res = sim.simulate(num_simulations=1000, seed=42)

    assert res["simulations_count"] == 1000
    # 5th percentile return must be <= 50th percentile (median) <= 95th percentile
    assert res["p5_return_pct"] <= res["median_return_pct"] <= res["p95_return_pct"]
    # Drawdown: 5th percentile dd <= median dd <= 95th percentile dd
    assert res["p5_drawdown_pct"] <= res["median_drawdown_pct"] <= res["p95_drawdown_pct"]
    assert "plot_json" in res
    assert "data" in res["plot_json"]
    assert "layout" in res["plot_json"]
