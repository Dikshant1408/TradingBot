"""
Backtesting Visualization and Report Generators using Plotly.
Produces Candlestick trade charts, equity curves, drawdown series, and CSV exports.
"""
import io
import json
from typing import Dict, List, Any
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class BacktestReportGenerator:
    """
    Generates interactive Plotly figures and tabular export formats.
    """

    @staticmethod
    def generate_candlestick_chart(
        df: pd.DataFrame,
        trades: List[Dict[str, Any]],
        symbol: str
    ) -> Dict[str, Any]:
        """
        Produce a Plotly Candlestick chart with entry and exit trade markers.
        """
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=(f"{symbol} Price Action & Executed Trades", "Volume"),
            row_heights=[0.75, 0.25]
        )

        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df["timestamp"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
                increasing_line_color="#00C087",  # Modern terminal green
                decreasing_line_color="#FF4D4D",  # Modern terminal red
                increasing_fillcolor="#00C087",
                decreasing_fillcolor="#FF4D4D"
            ),
            row=1, col=1
        )

        # Volume bars
        colors = ["#00C087" if c >= o else "#FF4D4D" for o, c in zip(df["open"], df["close"])]
        fig.add_trace(
            go.Bar(
                x=df["timestamp"],
                y=df["volume"],
                name="Volume",
                marker_color=colors,
                opacity=0.5
            ),
            row=2, col=1
        )

        # Overlay Buy and Sell Markers
        buy_times, buy_prices, buy_texts = [], [], []
        sell_times, sell_prices, sell_texts = [], [], []

        for t in trades:
            entry_t = t.get("entry_time")
            exit_t = t.get("exit_time")
            pnl = t.get("net_pnl", 0)
            pnl_str = f"+₹{pnl:.2f}" if pnl >= 0 else f"-₹{abs(pnl):.2f}"

            if t.get("side") == "LONG":
                buy_times.append(entry_t)
                buy_prices.append(t["entry_price"])
                buy_texts.append(f"BUY {t['quantity']} @ ₹{t['entry_price']:.2f}")

                if exit_t:
                    sell_times.append(exit_t)
                    sell_prices.append(t["exit_price"])
                    sell_texts.append(f"EXIT LONG @ ₹{t['exit_price']:.2f} ({pnl_str})")
            else:
                sell_times.append(entry_t)
                sell_prices.append(t["entry_price"])
                sell_texts.append(f"SHORT {t['quantity']} @ ₹{t['entry_price']:.2f}")

                if exit_t:
                    buy_times.append(exit_t)
                    buy_prices.append(t["exit_price"])
                    buy_texts.append(f"COVER SHORT @ ₹{t['exit_price']:.2f} ({pnl_str})")

        if buy_times:
            fig.add_trace(
                go.Scatter(
                    x=buy_times,
                    y=buy_prices,
                    mode="markers",
                    name="BUY / COVER",
                    marker=dict(symbol="triangle-up", size=11, color="#00E676", line=dict(width=1, color="#FFFFFF")),
                    text=buy_texts,
                    hoverinfo="text"
                ),
                row=1, col=1
            )

        if sell_times:
            fig.add_trace(
                go.Scatter(
                    x=sell_times,
                    y=sell_prices,
                    mode="markers",
                    name="SELL / EXIT",
                    marker=dict(symbol="triangle-down", size=11, color="#FF1744", line=dict(width=1, color="#FFFFFF")),
                    text=sell_texts,
                    hoverinfo="text"
                ),
                row=1, col=1
            )

        # Styling dark terminal aesthetic
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1318",
            plot_bgcolor="#141B22",
            font=dict(family="JetBrains Mono, monospace", color="#C9D1D9", size=11),
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=40, t=40, b=30),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(gridcolor="#21262D", zerolinecolor="#21262D")
        fig.update_yaxes(gridcolor="#21262D", zerolinecolor="#21262D")

        return json.loads(fig.to_json())

    @staticmethod
    def generate_equity_drawdown_chart(equity_series: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate interactive dual-axis Equity and Drawdown curve.
        """
        if not equity_series:
            return {}

        df = pd.DataFrame(equity_series)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["peak"] = df["equity"].cummax()
        df["drawdown_pct"] = ((df["peak"] - df["equity"]) / df["peak"]) * 100

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=("Portfolio Value (₹)", "Drawdown (%)"),
            row_heights=[0.7, 0.3]
        )

        # Equity curve
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["equity"],
                mode="lines",
                name="Total Equity",
                line=dict(color="#388BFD", width=2),
                fill="tozeroy",
                fillcolor="rgba(56, 139, 253, 0.08)"
            ),
            row=1, col=1
        )

        # Drawdown curve
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=-df["drawdown_pct"],
                mode="lines",
                name="Underwater Drawdown",
                line=dict(color="#F85149", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(248, 81, 73, 0.15)"
            ),
            row=2, col=1
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1318",
            plot_bgcolor="#141B22",
            font=dict(family="JetBrains Mono, monospace", color="#C9D1D9", size=11),
            margin=dict(l=50, r=40, t=40, b=30),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(gridcolor="#21262D")
        fig.update_yaxes(gridcolor="#21262D")

        return json.loads(fig.to_json())

    @staticmethod
    def export_trades_csv(trades: List[Dict[str, Any]]) -> str:
        """Export trades list to CSV format."""
        if not trades:
            return "Trade ID,Timestamp,Symbol,Side,Quantity,Entry,Exit,Gross P&L,Fees,Slippage,Net P&L,Strategy Reason\n"

        df = pd.DataFrame(trades)
        cols = [
            "trade_id", "entry_time", "symbol", "side", "quantity",
            "entry_price", "exit_price", "gross_pnl", "total_fees",
            "slippage_cost", "net_pnl", "strategy_reason"
        ]
        available_cols = [c for c in cols if c in df.columns]
        output = io.StringIO()
        df[available_cols].to_csv(output, index=False)
        return output.getvalue()
