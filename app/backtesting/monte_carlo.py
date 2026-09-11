"""
Monte Carlo Simulation Engine for Trading Strategy Robustness.
Performs bootstrap resampling of trade sequences to estimate drawdown confidence intervals.
"""
import json
from typing import List, Dict, Any, Optional
import numpy as np
import plotly.graph_objects as go


class MonteCarloSimulator:
    """
    Simulates thousands of alternative trade orderings to test strategy sensitivity to trade sequence.
    Supports both class-level run_simulation and instance-based simulate() calling conventions.
    """

    def __init__(self, trades: Optional[List[Dict[str, Any]]] = None, initial_capital: float = 100000.0):
        self.trades = trades or []
        self.initial_capital = initial_capital

    def simulate(self, num_simulations: int = 1000, seed: int = 42) -> Dict[str, Any]:
        return self.run_simulation(
            trades=self.trades,
            initial_capital=self.initial_capital,
            simulations=num_simulations,
            seed=seed
        )

    @classmethod
    def run_simulation(
        cls,
        trades: List[Dict[str, Any]],
        initial_capital: float = 100000.0,
        simulations: int = 1000,
        seed: int = 42
    ) -> Dict[str, Any]:
        empty_chart = json.loads(go.Figure().to_json())
        if not trades:
            return {
                "simulations_count": simulations,
                "simulations": simulations,
                "drawdown_p5": 0.0,
                "drawdown_median": 0.0,
                "drawdown_p95_worst": 0.0,
                "p5_drawdown_pct": 0.0,
                "median_drawdown_pct": 0.0,
                "p95_drawdown_pct": 0.0,
                "median_return_pct": 0.0,
                "p5_return_pct": 0.0,
                "p95_return_pct": 0.0,
                "equity_p5_worst": initial_capital,
                "equity_median": initial_capital,
                "equity_p95_best": initial_capital,
                "risk_of_ruin_pct": 0.0,
                "chart": empty_chart,
                "plot_json": empty_chart
            }

        np.random.seed(seed)
        net_pnls = np.array([float(t.get("net_pnl", 0.0)) for t in trades])
        n_trades = len(net_pnls)

        sim_max_drawdowns = []
        sim_final_equities = []
        sample_curves = []
        ruin_threshold = initial_capital * 0.50
        ruin_events = 0

        # Run bootstrap simulations
        for i in range(simulations):
            # Resample trade returns with replacement
            sampled_pnls = np.random.choice(net_pnls, size=n_trades, replace=True)
            equity_curve = initial_capital + np.cumsum(sampled_pnls)
            equity_curve = np.insert(equity_curve, 0, initial_capital)

            if np.any(equity_curve < ruin_threshold):
                ruin_events += 1

            # Drawdown calculation
            peak = np.maximum.accumulate(equity_curve)
            dd = (peak - equity_curve) / peak
            max_dd = float(np.max(dd)) * 100

            sim_max_drawdowns.append(max_dd)
            sim_final_equities.append(float(equity_curve[-1]))

            # Keep first 25 curves for background fan chart
            if i < 25:
                sample_curves.append(equity_curve.tolist())

        sim_max_drawdowns = np.array(sim_max_drawdowns)
        sim_final_equities = np.array(sim_final_equities)

        # Percentiles (5th, 50th median, 95th)
        dd_p5 = round(float(np.percentile(sim_max_drawdowns, 5)), 2)
        dd_p50 = round(float(np.percentile(sim_max_drawdowns, 50)), 2)
        dd_p95 = round(float(np.percentile(sim_max_drawdowns, 95)), 2)

        eq_p5 = round(float(np.percentile(sim_final_equities, 5)), 2)
        eq_p50 = round(float(np.percentile(sim_final_equities, 50)), 2)
        eq_p95 = round(float(np.percentile(sim_final_equities, 95)), 2)

        ret_p5 = round(((eq_p5 - initial_capital) / initial_capital) * 100, 2)
        ret_median = round(((eq_p50 - initial_capital) / initial_capital) * 100, 2)
        ret_p95 = round(((eq_p95 - initial_capital) / initial_capital) * 100, 2)

        ruin_risk_pct = round((ruin_events / simulations) * 100, 2)

        # Generate Plotly Fan Chart
        fig = go.Figure()

        trade_indices = list(range(n_trades + 1))
        for curve in sample_curves:
            fig.add_trace(go.Scatter(
                x=trade_indices,
                y=curve,
                mode="lines",
                line=dict(color="rgba(56, 139, 253, 0.1)", width=1),
                showlegend=False,
                hoverinfo="skip"
            ))

        fig.add_trace(go.Scatter(
            x=[0, n_trades],
            y=[initial_capital, eq_p50],
            mode="lines+markers",
            name="Median Equity (P50)",
            line=dict(color="#388BFD", width=2.5)
        ))

        fig.update_layout(
            title=f"Monte Carlo Bootstrap Simulation ({simulations} Iterations)",
            template="plotly_dark",
            paper_bgcolor="#0E1318",
            plot_bgcolor="#141B22",
            font=dict(family="JetBrains Mono, monospace", color="#C9D1D9", size=11),
            margin=dict(l=50, r=40, t=50, b=30),
            xaxis_title="Trade Number",
            yaxis_title="Portfolio Value (₹)",
            hovermode="x unified"
        )
        fig.update_xaxes(gridcolor="#21262D")
        fig.update_yaxes(gridcolor="#21262D")

        fig_dict = json.loads(fig.to_json())

        return {
            "simulations_count": simulations,
            "simulations": simulations,
            "drawdown_p5": dd_p5,
            "drawdown_median": dd_p50,
            "drawdown_p95_worst": dd_p95,
            "p5_drawdown_pct": dd_p5,
            "median_drawdown_pct": dd_p50,
            "p95_drawdown_pct": dd_p95,
            "median_return_pct": ret_median,
            "p5_return_pct": ret_p5,
            "p95_return_pct": ret_p95,
            "equity_p5_worst": eq_p5,
            "equity_median": eq_p50,
            "equity_p95_best": eq_p95,
            "risk_of_ruin_pct": ruin_risk_pct,
            "chart": fig_dict,
            "plot_json": fig_dict
        }
