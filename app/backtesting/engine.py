"""
Event-Driven Chronological Backtesting Engine.
Zero lookahead bias. Supports NEXT_OPEN (realistic) and SAME_CLOSE execution models.
Includes automated anti-bias diagnostic audit and Monte Carlo simulation.
"""
import uuid
import logging
from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime
from app.strategies.base import BaseStrategy, SignalAction, Signal
from app.backtesting.broker_simulator import BacktestBrokerSimulator
from app.backtesting.indian_costs import IndianCostCalculator
from app.backtesting.metrics import MetricsCalculator
from app.backtesting.reports import BacktestReportGenerator
from app.backtesting.execution_models import ExecutionModel
from app.backtesting.diagnostics import BacktestDiagnostics
from app.backtesting.monte_carlo import MonteCarloSimulator
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
        position_size_pct: float = 0.50,
        brokerage: float = 20.0,
        segment: str = "EQUITY_INTRADAY",
        slippage_pct: float = 0.0005,
        execution_model: ExecutionModel = ExecutionModel.NEXT_OPEN
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.execution_model = execution_model
        self.cost_calculator = IndianCostCalculator(
            brokerage_per_order=brokerage,
            segment=segment,
            slippage_pct=slippage_pct
        )
        self.broker = BacktestBrokerSimulator(
            initial_capital=initial_capital,
            cost_calculator=self.cost_calculator
        )

    def _execute_signal(
        self,
        sig: Signal,
        symbol: str,
        fill_price: float,
        timestamp: datetime,
        lot_size: int
    ) -> None:
        """Helper to execute an order in the simulator."""
        curr_price = fill_price
        candle_time = timestamp

        if sig.action == SignalAction.BUY:
            allocated_capital = self.broker.cash * self.position_size_pct
            raw_qty = int(allocated_capital / curr_price) if curr_price > 0 else 0
            qty = (raw_qty // lot_size) * lot_size
            if qty > 0:
                self.broker.execute_order(
                    symbol=symbol,
                    side="BUY",
                    quantity=qty,
                    price=curr_price,
                    timestamp=candle_time,
                    reason=sig.reason,
                    indicator_snapshot=sig.metadata
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
                    reason=sig.reason,
                    indicator_snapshot=sig.metadata
                )

        elif sig.action == SignalAction.SELL:
            pos = self.broker.positions.get(symbol)
            if pos and pos["side"] == "LONG":
                self.broker.execute_order(
                    symbol=symbol,
                    side="SELL",
                    quantity=pos["quantity"],
                    price=curr_price,
                    timestamp=candle_time,
                    reason=sig.reason,
                    indicator_snapshot=sig.metadata
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
                        reason=sig.reason,
                        indicator_snapshot=sig.metadata
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
        logger.info(
            f"Starting backtest {run_id} on {symbol} with {len(df)} candles "
            f"[Execution Model: {self.execution_model.value}]..."
        )

        instrument = instrument_registry.get(symbol)
        lot_size = instrument.lot_size if instrument else 1

        pending_signals: List[Signal] = []

        # Chronological candle loop
        for i in range(len(df)):
            candle = df.iloc[i]
            candle_time = pd.to_datetime(candle["timestamp"])

            # 1. If NEXT_OPEN, execute pending orders from previous bar close at this bar's OPEN price
            if self.execution_model == ExecutionModel.NEXT_OPEN and pending_signals:
                open_price = float(candle["open"])
                for sig in pending_signals:
                    self._execute_signal(sig, symbol, open_price, candle_time, lot_size)
                pending_signals = []

            # 2. Strategy evaluation at candle close (strictly historical up to i)
            history = df.iloc[:i + 1]
            portfolio_state = {
                "cash": self.broker.cash,
                "positions": self.broker.positions
            }
            signals = self.strategy.on_bar(candle, history, portfolio_state)

            # 3. Handle generated signals
            if self.execution_model == ExecutionModel.NEXT_OPEN:
                # Queue for next bar open
                if i < len(df) - 1:
                    pending_signals.extend(signals)
            else:
                # SAME_CLOSE: execute immediately at this candle close
                close_price = float(candle["close"])
                for sig in signals:
                    self._execute_signal(sig, symbol, close_price, candle_time, lot_size)

            # 4. Snapshot portfolio equity at candle close
            curr_close = float(candle["close"])
            equity = self.broker.get_portfolio_equity({symbol: curr_close})
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
                reason="Backtest period ended: Final bar close liquidation",
                indicator_snapshot={"final_liquidation": True}
            )
            self.broker.equity_history[-1]["equity"] = round(self.broker.cash, 2)

        # 6. Calculate comprehensive metrics
        metrics = MetricsCalculator.calculate(
            initial_capital=self.initial_capital,
            equity_series=self.broker.equity_history,
            trades=self.broker.closed_trades
        )

        # 7. Quality & Bias Diagnostics
        diagnostics = BacktestDiagnostics.audit(metrics, self.broker.closed_trades, df)

        # 8. Monte Carlo Simulation (1,000 iterations)
        monte_carlo = MonteCarloSimulator.run_simulation(
            trades=self.broker.closed_trades,
            initial_capital=self.initial_capital,
            simulations=1000
        )

        # 9. Interactive Visualizations
        candlestick_chart = BacktestReportGenerator.generate_candlestick_chart(
            df=df,
            trades=self.broker.closed_trades,
            symbol=symbol
        )

        equity_chart = BacktestReportGenerator.generate_equity_drawdown_chart(
            equity_series=self.broker.equity_history
        )

        logger.info(
            f"Backtest {run_id} completed [{self.execution_model.value}]. "
            f"Return: {metrics['return_pct']}%, Trades: {metrics['total_trades']}, "
            f"WinRate: {metrics['win_rate']}%, MaxDD: {metrics['max_drawdown']}%, "
            f"Robustness: {diagnostics['grade']}"
        )

        return {
            "id": run_id,
            "strategy_name": self.strategy.name,
            "strategy_version": self.strategy.version,
            "symbol": symbol,
            "execution_model": self.execution_model.value,
            "start_date": str(df["timestamp"].iloc[0]),
            "end_date": str(df["timestamp"].iloc[-1]),
            "parameters": self.strategy.parameters,
            "metrics": metrics,
            "diagnostics": diagnostics,
            "monte_carlo": monte_carlo,
            "trades": self.broker.closed_trades,
            "equity_curve": self.broker.equity_history,
            "candlestick_chart": candlestick_chart,
            "equity_chart": equity_chart
        }
