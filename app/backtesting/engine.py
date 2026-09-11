"""
Event-Driven Chronological Backtesting Engine.
Zero lookahead bias. Simulates candle-by-candle market evolution and realistic Indian market fills.
"""
import uuid
import logging
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime
from app.strategies.base import BaseStrategy, SignalAction
from app.backtesting.broker_simulator import BacktestBrokerSimulator
from app.backtesting.indian_costs import IndianCostCalculator
from app.backtesting.metrics import MetricsCalculator
from app.backtesting.reports import BacktestReportGenerator
from app.data.instruments import instrument_registry

logger = logging.getLogger("trading_bot.backtesting.engine")


class BacktestEngine:
    """
    Event-driven backtesting engine running candle-by-candle.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 100000.0,
        position_size_pct: float = 0.50,  # Max 50% capital per trade
        brokerage: float = 20.0,
        stt_rate: float = 0.00025,
        slippage_pct: float = 0.0005
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.cost_calculator = IndianCostCalculator(
            brokerage_per_order=brokerage,
            stt_rate=stt_rate,
            slippage_pct=slippage_pct
        )
        self.broker = BacktestBrokerSimulator(
            initial_capital=initial_capital,
            cost_calculator=self.cost_calculator
        )

    def run(
        self,
        df: pd.DataFrame,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Execute chronological backtest on historical OHLCV data.
        """
        if df.empty:
            raise ValueError("Historical DataFrame is empty.")

        run_id = str(uuid.uuid4())
        logger.info(f"Starting backtest {run_id} on {symbol} with {len(df)} candles...")

        instrument = instrument_registry.get(symbol)
        lot_size = instrument.lot_size if instrument else 1

        # Chronological candle loop
        for i in range(len(df)):
            candle = df.iloc[i]
            # Strictly up to candle i (zero lookahead)
            history = df.iloc[:i + 1]

            curr_price = float(candle["close"])
            candle_time = pd.to_datetime(candle["timestamp"])

            # 1. Provide portfolio snapshot to strategy
            portfolio_state = {
                "cash": self.broker.cash,
                "positions": self.broker.positions
            }

            # 2. Strategy evaluation
            signals = self.strategy.on_bar(candle, history, portfolio_state)

            # 3. Execution of signals
            for sig in signals:
                if sig.action == SignalAction.BUY:
                    # Calculate quantity based on position_size_pct
                    allocated_capital = self.broker.cash * self.position_size_pct
                    raw_qty = int(allocated_capital / curr_price) if curr_price > 0 else 0
                    # Round down to valid lot size
                    qty = (raw_qty // lot_size) * lot_size
                    if qty > 0:
                        self.broker.execute_order(
                            symbol=symbol,
                            side="BUY",
                            quantity=qty,
                            price=curr_price,
                            timestamp=candle_time,
                            reason=sig.reason
                        )

                elif sig.action == SignalAction.EXIT:
                    pos = self.broker.positions.get(symbol)
                    if pos:
                        self.broker.execute_order(
                            symbol=symbol,
                            side="EXIT",
                            quantity=pos["quantity"],
                            price=curr_price,
                            timestamp=candle_time,
                            reason=sig.reason
                        )

                elif sig.action == SignalAction.SELL:
                    # Short position or exit
                    pos = self.broker.positions.get(symbol)
                    if pos and pos["side"] == "LONG":
                        self.broker.execute_order(
                            symbol=symbol,
                            side="SELL",
                            quantity=pos["quantity"],
                            price=curr_price,
                            timestamp=candle_time,
                            reason=sig.reason
                        )
                    else:
                        allocated_capital = self.broker.cash * self.position_size_pct
                        raw_qty = int(allocated_capital / curr_price) if curr_price > 0 else 0
                        qty = (raw_qty // lot_size) * lot_size
                        if qty > 0:
                            self.broker.execute_order(
                                symbol=symbol,
                                side="SELL",
                                quantity=qty,
                                price=curr_price,
                                timestamp=candle_time,
                                reason=sig.reason
                            )

            # 4. Snapshot portfolio equity at this candle
            equity = self.broker.get_portfolio_equity({symbol: curr_price})
            self.broker.equity_history.append({
                "timestamp": candle["timestamp"],
                "equity": equity
            })

        # 5. Liquidate any open position at the final candle close
        last_candle = df.iloc[-1]
        last_price = float(last_candle["close"])
        last_time = pd.to_datetime(last_candle["timestamp"])

        if symbol in self.broker.positions:
            pos = self.broker.positions[symbol]
            side_to_close = "EXIT" if pos["side"] == "LONG" else "BUY"
            self.broker.execute_order(
                symbol=symbol,
                side=side_to_close,
                quantity=pos["quantity"],
                price=last_price,
                timestamp=last_time,
                reason="Backtest period ended: Final bar close liquidation"
            )
            # Record final equity
            self.broker.equity_history[-1]["equity"] = round(self.broker.cash, 2)

        # 6. Calculate comprehensive metrics
        metrics = MetricsCalculator.calculate(
            initial_capital=self.initial_capital,
            equity_series=self.broker.equity_history,
            trades=self.broker.closed_trades
        )

        # 7. Generate interactive visualizations
        candlestick_chart = BacktestReportGenerator.generate_candlestick_chart(
            df=df,
            trades=self.broker.closed_trades,
            symbol=symbol
        )

        equity_chart = BacktestReportGenerator.generate_equity_drawdown_chart(
            equity_series=self.broker.equity_history
        )

        logger.info(
            f"Backtest {run_id} completed. Return: {metrics['return_pct']}%, "
            f"Trades: {metrics['total_trades']}, WinRate: {metrics['win_rate']}%, "
            f"MaxDD: {metrics['max_drawdown']}%"
        )

        return {
            "id": run_id,
            "strategy_name": self.strategy.name,
            "strategy_version": self.strategy.version,
            "symbol": symbol,
            "start_date": str(df["timestamp"].iloc[0]),
            "end_date": str(df["timestamp"].iloc[-1]),
            "parameters": self.strategy.parameters,
            "metrics": metrics,
            "trades": self.broker.closed_trades,
            "equity_curve": self.broker.equity_history,
            "candlestick_chart": candlestick_chart,
            "equity_chart": equity_chart
        }
