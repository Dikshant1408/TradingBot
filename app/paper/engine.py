"""
Paper Trading Execution Engine.
Orchestrates simulated broker, bar processing, risk screening, and real-time state broadcasts.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timezone
from app.brokers.adapters.paper_adapter import PaperBroker
from app.strategies.base import BaseStrategy, SignalAction
from app.risk.manager import risk_manager
from app.core.state import state_manager, BotStatus, TradingMode
from app.core.event_bus import event_bus, EventType
from app.data.instruments import instrument_registry

logger = logging.getLogger("trading_bot.paper.engine")


class PaperTradingEngine:
    """
    Manages active paper trading sessions (Replay or Market Polling).
    """

    def __init__(self):
        self.broker = PaperBroker()
        self.strategy: Optional[BaseStrategy] = None
        self.symbol: str = "NIFTY50_DEMO"
        self.dataset: Optional[pd.DataFrame] = None
        self.current_bar_index: int = 0
        self.is_running: bool = False
        self.replay_task: Optional[asyncio.Task] = None
        self.replay_delay_seconds: float = 0.5

    def configure(
        self,
        strategy: BaseStrategy,
        symbol: str,
        dataset: pd.DataFrame,
        initial_capital: float = 100000.0,
        replay_delay_seconds: float = 0.5
    ) -> None:
        """Initialize session parameters."""
        self.strategy = strategy
        self.symbol = symbol.upper()
        self.dataset = dataset
        self.current_bar_index = 0
        self.replay_delay_seconds = replay_delay_seconds
        self.broker = PaperBroker(initial_capital=initial_capital)

        state_manager.update(
            mode=TradingMode.PAPER,
            status=BotStatus.IDLE,
            active_strategy=strategy.name,
            active_symbol=self.symbol,
            cash=initial_capital,
            total_equity=initial_capital,
            today_pnl=0.0,
            today_trades_count=0
        )
        logger.info(f"PaperTradingEngine configured for {self.symbol} with {strategy.name}")

    def start(self) -> None:
        """Start or resume the paper trading processing loop."""
        if state_manager.state.is_emergency_stopped:
            raise RuntimeError("Cannot start: Emergency Stop is active. Reset first.")
        if state_manager.state.is_kill_switch_active:
            raise RuntimeError("Cannot start: Kill switch is active.")

        self.is_running = True
        state_manager.update(status=BotStatus.RUNNING)
        event_bus.emit(EventType.STATUS_CHANGED, {"status": "RUNNING"})

        # Spawn background replay task if loop is running
        try:
            loop = asyncio.get_running_loop()
            if self.replay_task is None or self.replay_task.done():
                self.replay_task = loop.create_task(self._run_loop())
        except RuntimeError:
            pass

    def pause(self) -> None:
        """Pause processing without liquidating positions."""
        self.is_running = False
        state_manager.update(status=BotStatus.PAUSED)
        event_bus.emit(EventType.STATUS_CHANGED, {"status": "PAUSED"})
        logger.info("Paper trading session PAUSED.")

    def stop(self) -> None:
        """Stop processing session."""
        self.is_running = False
        if self.replay_task and not self.replay_task.done():
            self.replay_task.cancel()
        state_manager.update(status=BotStatus.IDLE)
        event_bus.emit(EventType.STATUS_CHANGED, {"status": "IDLE"})
        logger.info("Paper trading session STOPPED.")

    def emergency_stop(self, reason: str = "Emergency stop requested by user") -> None:
        """Trigger emergency stop: halt immediately and block further execution."""
        self.is_running = False
        if self.replay_task and not self.replay_task.done():
            self.replay_task.cancel()

        state_manager.trigger_emergency_stop(reason)
        event_bus.emit(EventType.EMERGENCY_STOP, {"reason": reason})
        logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")

    def reset_emergency_stop(self) -> None:
        """Manually reset emergency stop state."""
        state_manager.reset_emergency_stop()
        event_bus.emit(EventType.STATUS_CHANGED, {"status": "IDLE"})
        logger.info("Emergency stop has been manually reset.")

    def process_candle(self, candle: pd.Series, history: pd.DataFrame) -> Dict[str, Any]:
        """
        Process a single new candle through strategy and risk rules.
        """
        curr_price = float(candle["close"])
        candle_time = pd.to_datetime(candle["timestamp"])

        # 1. Update broker position mark-to-market prices
        self.broker.update_market_price(self.symbol, curr_price)

        # 2. Strategy evaluation
        portfolio_state = {
            "cash": self.broker.cash,
            "positions": self.broker.positions
        }
        signals = self.strategy.on_bar(candle, history, portfolio_state) if self.strategy else []

        instrument = instrument_registry.get(self.symbol)
        lot_size = instrument.lot_size if instrument else 1

        executed_orders = []

        # 3. Risk check and order execution for each signal
        for sig in signals:
            event_bus.emit(EventType.SIGNAL_GENERATED, sig.model_dump())
            state_manager.update(last_signal=sig.model_dump())

            qty = 0
            if sig.action == SignalAction.BUY:
                allocated = self.broker.cash * 0.50
                raw_qty = int(allocated / curr_price) if curr_price > 0 else 0
                qty = (raw_qty // lot_size) * lot_size
            elif sig.action in [SignalAction.EXIT, SignalAction.SELL]:
                pos = self.broker.positions.get(self.symbol)
                qty = pos["quantity"] if pos else 0

            if qty > 0:
                # Pre-trade risk evaluation
                allowed, reject_reason = risk_manager.evaluate_order(
                    symbol=self.symbol,
                    side=sig.action.value,
                    quantity=qty,
                    price=curr_price,
                    current_state=state_manager.state
                )

                if allowed:
                    order = self.broker.place_order(
                        symbol=self.symbol,
                        side=sig.action.value,
                        quantity=qty,
                        price=curr_price,
                        stop_loss=sig.stop_loss,
                        target=sig.target,
                        reason=sig.reason,
                        indicator_snapshot=sig.metadata
                    )
                    executed_orders.append(order)
                    state_manager.update(
                        last_execution=order,
                        today_trades_count=len(self.broker.trades)
                    )
                else:
                    logger.warning(f"Risk Manager rejected order: {reject_reason}")
                    event_bus.emit(EventType.ORDER_REJECTED, {
                        "symbol": self.symbol,
                        "side": sig.action.value,
                        "quantity": qty,
                        "reason": reject_reason
                    })

        # 4. Update state manager snapshot
        acc = self.broker.get_account()
        peak = max(state_manager.state.peak_equity, acc["total_equity"])
        dd = (peak - acc["total_equity"]) / peak if peak > 0 else 0.0

        state_manager.update(
            cash=acc["cash"],
            invested_value=acc["invested_value"],
            total_equity=acc["total_equity"],
            today_pnl=acc["today_pnl"],
            today_realized_pnl=acc["realized_pnl"],
            today_unrealized_pnl=acc["unrealized_pnl"],
            drawdown_pct=dd,
            peak_equity=peak,
            open_positions_count=acc["open_positions_count"],
            today_trades_count=len(self.broker.trades)
        )

        event_bus.emit(EventType.PORTFOLIO_UPDATED, acc)

        return {
            "candle": candle.to_dict(),
            "signals": [s.model_dump() for s in signals],
            "executed_orders": executed_orders,
            "account": acc
        }

    async def _run_loop(self) -> None:
        """Background asynchronous runner stepping through bars."""
        logger.info(f"Starting paper trading candle loop from index {self.current_bar_index}...")
        try:
            while self.is_running and self.dataset is not None:
                if self.current_bar_index >= len(self.dataset):
                    logger.info("Reached end of replay dataset.")
                    self.stop()
                    break

                candle = self.dataset.iloc[self.current_bar_index]
                history = self.dataset.iloc[:self.current_bar_index + 1]

                self.process_candle(candle, history)
                self.current_bar_index += 1

                await asyncio.sleep(self.replay_delay_seconds)
        except asyncio.CancelledError:
            logger.info("Paper trading replay loop was cancelled.")
        except Exception as e:
            logger.error(f"Error in paper trading loop: {e}", exc_info=True)
            self.stop()


# Global PaperTradingEngine singleton
paper_engine = PaperTradingEngine()
