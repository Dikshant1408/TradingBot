"""
CLI Interface for local execution, backtesting, and status checks.
Usage:
    python -m app.cli status
    python -m app.cli backtest --strategy MA_Crossover --symbol NIFTY50_DEMO
    python -m app.cli paper --symbol NIFTY50_DEMO --steps 10
"""
import sys
import argparse
import json

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config.settings import get_settings
from app.data.loader import DataLoader, initialize_demo_data
from app.strategies.registry import strategy_registry
from app.backtesting.engine import BacktestEngine
from app.core.state import state_manager
from app.core.clock import get_ist_now, is_market_open_now

settings = get_settings()


def run_status():
    """Print current workstation status to console."""
    is_open, msg = is_market_open_now()
    ist_time = get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")

    print("\n" + "=" * 55)
    print(f"       QUANTDESK INDIA - TERMINAL STATUS")
    print("=" * 55)
    print(f" Current Time (IST): {ist_time}")
    print(f" Market Session:     {'OPEN' if is_open else 'CLOSED'} ({msg})")
    print(f" Mode:               {settings.APP_MODE.upper()}")
    print(f" Bot Status:         {state_manager.state.status.value}")
    print(f" Kill Switch:        {'ACTIVE (LOCKED)' if state_manager.state.is_kill_switch_active else 'INACTIVE'}")
    print(f" Emergency Stop:     {'ENGAGED' if state_manager.state.is_emergency_stopped else 'INACTIVE'}")
    print(f" Virtual Capital:    ₹{state_manager.state.cash:,.2f}")
    print(f" Today's P&L:        ₹{state_manager.state.today_pnl:,.2f}")
    print("=" * 55 + "\n")


def run_backtest_cli(strategy_name: str, symbol: str, fast_ma: int, slow_ma: int, capital: float):
    """Run backtest from CLI and display results table."""
    initialize_demo_data()
    df = DataLoader.get_processed(symbol)
    if df is None:
        sample = settings.DATA_DIR / "samples" / f"{symbol.upper()}.csv"
        if sample.exists():
            df, _ = DataLoader.load_csv(sample, symbol)
        else:
            sample = DataLoader.generate_demo_dataset(symbol)
            df, _ = DataLoader.load_csv(sample, symbol)

    strategy = strategy_registry.create(
        strategy_name,
        parameters={"fast_period": fast_ma, "slow_period": slow_ma}
    )

    print(f"\nRunning backtest: {strategy_name} (Fast={fast_ma}, Slow={slow_ma}) on {symbol}...")
    engine = BacktestEngine(strategy=strategy, initial_capital=capital)
    res = engine.run(df, symbol=symbol)
    m = res["metrics"]

    print("\n" + "=" * 55)
    print(f"       BACKTEST RESULTS: {symbol} ({strategy_name})")
    print("=" * 55)
    print(f" Initial Capital:     ₹{m['initial_capital']:,.2f}")
    print(f" Final Capital:       ₹{m['final_capital']:,.2f}")
    print(f" Net P&L:             ₹{m['net_pnl']:,.2f} ({m['return_pct']}%)")
    print(f" Total Trades:        {m['total_trades']} (Win Rate: {m['win_rate']}%)")
    print(f" Profit Factor:       {m['profit_factor']}")
    print(f" Max Drawdown:        {m['max_drawdown']}% (₹{m['max_drawdown_amount']:,.2f})")
    print(f" Sharpe Ratio:        {m['sharpe_ratio']} (Benchmark: 6.5%)")
    print(f" Total Fees Paid:     ₹{m['total_fees']:,.2f}")
    print(f" Slippage Incurred:   ₹{m['slippage_cost']:,.2f}")
    print("=" * 55 + "\n")


def main():
    parser = argparse.ArgumentParser(description="QuantDesk India CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status
    subparsers.add_parser("status", help="Display system and market status")

    # Backtest
    bt_parser = subparsers.add_parser("backtest", help="Execute backtest")
    bt_parser.add_argument("--strategy", default="MA_Crossover", help="Strategy ID")
    bt_parser.add_argument("--symbol", default="NIFTY50_DEMO", help="Symbol")
    bt_parser.add_argument("--fast", type=int, default=20, help="Fast MA period")
    bt_parser.add_argument("--slow", type=int, default=50, help="Slow MA period")
    bt_parser.add_argument("--capital", type=float, default=100000.0, help="Initial capital in INR")

    args = parser.parse_args()

    if args.command == "status":
        run_status()
    elif args.command == "backtest":
        run_backtest_cli(args.strategy, args.symbol, args.fast, args.slow, args.capital)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
