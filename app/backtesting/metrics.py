"""
Quantitative backtest performance metrics calculation.
Calculates risk-adjusted returns (Sharpe, Sortino), drawdown series, win rate, and CAGR.
"""
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np


class MetricsCalculator:
    """
    Computes factual backtesting performance statistics.
    COMPLIANCE NOTE (Section 39): Pure factual outputs, no misleading or exaggerated claims.
    """

    @staticmethod
    def calculate(
        initial_capital: float,
        equity_series: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        risk_free_rate: float = 0.065  # 6.5% Indian 10-Yr G-Sec / T-Bill benchmark
    ) -> Dict[str, Any]:
        if not equity_series:
            return {
                "initial_capital": initial_capital,
                "final_capital": initial_capital,
                "net_pnl": 0.0,
                "return_pct": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0
            }

        final_capital = equity_series[-1]["equity"]
        net_pnl = round(final_capital - initial_capital, 2)
        return_pct = round((net_pnl / initial_capital) * 100, 2)

        # Equity dataframe
        eq_df = pd.DataFrame(equity_series)
        eq_df["timestamp"] = pd.to_datetime(eq_df["timestamp"])
        eq_df = eq_df.sort_values("timestamp")

        # Peak & Drawdown
        eq_df["peak"] = eq_df["equity"].cummax()
        eq_df["drawdown"] = (eq_df["peak"] - eq_df["equity"]) / eq_df["peak"]
        max_drawdown = float(eq_df["drawdown"].max()) if not eq_df.empty else 0.0
        max_drawdown_amount = float((eq_df["peak"] - eq_df["equity"]).max()) if not eq_df.empty else 0.0

        # Calculate CAGR if more than 1 day
        cagr = 0.0
        if len(eq_df) > 1:
            total_days = max((eq_df["timestamp"].iloc[-1] - eq_df["timestamp"].iloc[0]).days, 1)
            years = total_days / 365.25
            if years > 0 and final_capital > 0:
                cagr = round(((final_capital / initial_capital) ** (1 / years) - 1) * 100, 2)

        # Daily returns for Sharpe & Sortino
        eq_df["daily_return"] = eq_df["equity"].pct_change().fillna(0)
        daily_returns = eq_df["daily_return"]

        # Annualized Sharpe Ratio (252 trading days)
        daily_rf = risk_free_rate / 252
        excess_returns = daily_returns - daily_rf
        std_dev = daily_returns.std()
        sharpe_ratio = 0.0
        if std_dev > 0:
            sharpe_ratio = round(float(np.sqrt(252) * excess_returns.mean() / std_dev), 2)

        # Annualized Sortino Ratio (Downside deviation)
        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = 0.0
        if downside_std > 0 and not pd.isna(downside_std):
            sortino_ratio = round(float(np.sqrt(252) * excess_returns.mean() / downside_std), 2)

        # Trade-level statistics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get("net_pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("net_pnl", 0) < 0]
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = round((win_count / total_trades) * 100, 2) if total_trades > 0 else 0.0

        gross_wins = sum(t.get("net_pnl", 0) for t in winning_trades)
        gross_losses = abs(sum(t.get("net_pnl", 0) for t in losing_trades))
        profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)

        avg_win = round(gross_wins / win_count, 2) if win_count > 0 else 0.0
        avg_loss = round(gross_losses / loss_count, 2) if loss_count > 0 else 0.0
        avg_trade = round(net_pnl / total_trades, 2) if total_trades > 0 else 0.0

        largest_win = max([t.get("net_pnl", 0) for t in trades], default=0.0)
        largest_loss = min([t.get("net_pnl", 0) for t in trades], default=0.0)

        total_fees = round(sum(t.get("total_fees", 0) for t in trades), 2)
        total_slippage = round(sum(t.get("slippage_cost", 0) for t in trades), 2)

        return {
            "initial_capital": round(initial_capital, 2),
            "final_capital": round(final_capital, 2),
            "net_pnl": net_pnl,
            "return_pct": return_pct,
            "cagr": cagr,
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": round(max_drawdown * 100, 2),  # In percentage
            "max_drawdown_amount": round(max_drawdown_amount, 2),
            "average_win": avg_win,
            "average_loss": avg_loss,
            "average_trade": avg_trade,
            "largest_winning_trade": round(largest_win, 2),
            "largest_losing_trade": round(largest_loss, 2),
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "total_fees": total_fees,
            "slippage_cost": total_slippage
        }
