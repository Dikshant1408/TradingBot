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

        # 1. Long vs Short breakdown
        long_trades = [t for t in trades if t.get("side") == "LONG"]
        short_trades = [t for t in trades if t.get("side") == "SHORT"]

        long_wins = [t for t in long_trades if t.get("net_pnl", 0) > 0]
        short_wins = [t for t in short_trades if t.get("net_pnl", 0) > 0]

        long_win_rate = round((len(long_wins) / len(long_trades)) * 100, 1) if long_trades else 0.0
        short_win_rate = round((len(short_wins) / len(short_trades)) * 100, 1) if short_trades else 0.0
        long_net_pnl = round(sum(t.get("net_pnl", 0) for t in long_trades), 2)
        short_net_pnl = round(sum(t.get("net_pnl", 0) for t in short_trades), 2)

        # 2. Day-of-Week Performance
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        day_stats = {d: {"trades": 0, "wins": 0, "net_pnl": 0.0, "win_rate": 0.0} for d in day_names}

        for t in trades:
            try:
                entry_dt = pd.to_datetime(t.get("entry_time"))
                weekday_idx = entry_dt.weekday()
                if 0 <= weekday_idx <= 4:
                    d_name = day_names[weekday_idx]
                    day_stats[d_name]["trades"] += 1
                    pnl = t.get("net_pnl", 0.0)
                    day_stats[d_name]["net_pnl"] = round(day_stats[d_name]["net_pnl"] + pnl, 2)
                    if pnl > 0:
                        day_stats[d_name]["wins"] += 1
            except Exception:
                pass

        for d_name in day_names:
            cnt = day_stats[d_name]["trades"]
            if cnt > 0:
                day_stats[d_name]["win_rate"] = round((day_stats[d_name]["wins"] / cnt) * 100, 1)

        # 3. Monthly Return Matrix
        monthly_matrix = {}
        if not eq_df.empty:
            try:
                eq_df["year"] = eq_df["timestamp"].dt.year
                eq_df["month"] = eq_df["timestamp"].dt.month

                for (year, month), group in eq_df.groupby(["year", "month"]):
                    year_str = str(year)
                    if year_str not in monthly_matrix:
                        monthly_matrix[year_str] = {}
                    month_start_eq = group["equity"].iloc[0]
                    month_end_eq = group["equity"].iloc[-1]
                    m_ret = round(((month_end_eq - month_start_eq) / month_start_eq) * 100, 2) if month_start_eq > 0 else 0.0
                    monthly_matrix[year_str][month] = m_ret
            except Exception:
                pass

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
            "slippage_cost": total_slippage,
            "long_short_breakdown": {
                "long_trades": len(long_trades),
                "long_win_rate": long_win_rate,
                "long_net_pnl": long_net_pnl,
                "short_trades": len(short_trades),
                "short_win_rate": short_win_rate,
                "short_net_pnl": short_net_pnl,
            },
            "day_of_week": day_stats,
            "monthly_matrix": monthly_matrix
        }
