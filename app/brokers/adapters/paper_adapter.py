"""
Paper Trading Broker Adapter.
Simulates realistic order execution, virtual cash accounting, and position tracking.
Zero live money risk.
"""
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from app.brokers.base import BaseBroker
from app.backtesting.indian_costs import IndianCostCalculator, TradeCostBreakdown
from app.core.event_bus import event_bus, EventType
from app.core.state import state_manager
from app.data.instruments import instrument_registry

logger = logging.getLogger("trading_bot.brokers.paper")


class PaperBroker(BaseBroker):
    """
    Virtual broker executing paper orders with realistic Indian costs and slippage.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        cost_calculator: Optional[IndianCostCalculator] = None,
        allow_shorting: bool = False
    ):
        self._is_live = False
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.cost_calculator = cost_calculator or IndianCostCalculator()
        self.allow_shorting = allow_shorting

        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.trades: List[Dict[str, Any]] = []
        self.today_pnl = 0.0
        self.realized_pnl = 0.0

    @property
    def is_live(self) -> bool:
        return False

    def get_account(self) -> Dict[str, Any]:
        long_invested = sum(
            pos["current_price"] * pos["quantity"]
            for pos in self.positions.values() if pos.get("side", "LONG") == "LONG"
        )
        short_collateral = sum(
            pos.get("collateral_held", pos["entry_price"] * pos["quantity"]) +
            ((pos["entry_price"] - pos["current_price"]) * pos["quantity"])
            for pos in self.positions.values() if pos.get("side") == "SHORT"
        )
        unrealized = sum(pos.get("unrealized_pnl", 0.0) for pos in self.positions.values())
        total_equity = self.cash + long_invested + short_collateral
        return {
            "mode": "PAPER",
            "cash": round(self.cash, 2),
            "invested_value": round(long_invested + short_collateral, 2),
            "total_equity": round(total_equity, 2),
            "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "today_pnl": round(self.today_pnl + unrealized, 2),
            "open_positions_count": len(self.positions),
            "total_orders_count": len(self.orders),
            "allow_shorting": self.allow_shorting
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions.values())

    def get_orders(self) -> List[Dict[str, Any]]:
        return sorted(self.orders, key=lambda x: x["timestamp"], reverse=True)

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        # Checked via data providers or cached market candle
        pos = self.positions.get(symbol)
        if pos:
            return {"symbol": symbol, "price": pos["current_price"]}
        return None

    def update_market_price(self, symbol: str, current_price: float) -> None:
        """Update current price of active position and recalculate unrealized PnL."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos["current_price"] = current_price
            if pos["side"] == "LONG":
                pos["unrealized_pnl"] = round((current_price - pos["entry_price"]) * pos["quantity"], 2)
            else:
                pos["unrealized_pnl"] = round((pos["entry_price"] - current_price) * pos["quantity"], 2)

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        reason: str = "",
        indicator_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Simulate order fill at current price with realistic slippage, simulated latency, and statutory costs.
        """
        now = datetime.now(timezone.utc)
        order_id = str(uuid.uuid4())

        if price is None or price <= 0:
            raise ValueError(f"Invalid execution price: {price}")

        # Slippage adjustment
        slippage_factor = self.cost_calculator.slippage_pct
        if side.upper() == "BUY":
            fill_price = round(price * (1.0 + slippage_factor), 2)
        else:
            fill_price = round(price * (1.0 - slippage_factor), 2)

        # Statutory Indian transaction costs with date-awareness
        costs = self.cost_calculator.calculate(side, fill_price, quantity, timestamp=now)
        trade_value = fill_price * quantity

        # Simulated gateway latency (e.g. 35-65ms on fast broadband)
        simulated_latency_ms = 48.5

        order_record = {
            "order_id": order_id,
            "mode": "PAPER",
            "symbol": symbol,
            "side": side.upper(),
            "quantity": quantity,
            "order_type": order_type,
            "price": fill_price,
            "status": "FILLED",
            "latency_ms": simulated_latency_ms,
            "stop_loss": stop_loss,
            "target": target,
            "costs": costs.model_dump(),
            "reason": reason,
            "indicator_snapshot": indicator_snapshot or {},
            "timestamp": now.isoformat()
        }
        self.orders.append(order_record)
        event_bus.emit(EventType.ORDER_SUBMITTED, order_record)

        pos = self.positions.get(symbol)

        if side.upper() == "BUY":
            # If closing an existing SHORT position
            if pos and pos["side"] == "SHORT":
                close_qty = min(pos["quantity"], quantity)
                entry_costs_for_close = round(pos.get("entry_costs", 0.0) * (close_qty / pos["quantity"]), 2)
                proportional_collateral = round(pos.get("collateral_held", pos["entry_price"] * pos["quantity"]) * (close_qty / pos["quantity"]), 2)

                costs = self.cost_calculator.calculate("BUY", fill_price, close_qty, timestamp=now)
                gross_pnl = (pos["entry_price"] - fill_price) * close_qty
                net_pnl = gross_pnl - costs.total_costs - entry_costs_for_close

                self.cash += (proportional_collateral + gross_pnl - costs.total_costs)
                self.realized_pnl += net_pnl
                self.today_pnl += net_pnl

                trade_record = {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "side": "SHORT",
                    "action": "BUY_TO_CLOSE",
                    "quantity": close_qty,
                    "entry_time": pos["entry_time"],
                    "exit_time": now.isoformat(),
                    "entry_price": pos["entry_price"],
                    "exit_price": fill_price,
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "total_fees": round(costs.total_costs + entry_costs_for_close, 2),
                    "slippage_cost": round(costs.slippage, 2),
                    "strategy_reason": reason,
                    "indicator_snapshot": indicator_snapshot or pos.get("indicator_snapshot", {}),
                    "cost_regime": costs.cost_regime,
                    "is_partial": (close_qty < pos["quantity"])
                }
                self.trades.append(trade_record)

                # PARTIAL POSITION RETENTION
                remaining_qty = pos["quantity"] - close_qty
                if remaining_qty > 0:
                    pos["quantity"] = remaining_qty
                    pos["collateral_held"] = max(0.0, round(pos.get("collateral_held", 0.0) - proportional_collateral, 2))
                    pos["entry_costs"] = max(0.0, round(pos.get("entry_costs", 0.0) - entry_costs_for_close, 2))
                    pos["unrealized_pnl"] = round((pos["entry_price"] - pos["current_price"]) * remaining_qty, 2)
                else:
                    del self.positions[symbol]

                event_bus.emit(EventType.ORDER_FILLED, trade_record)
                return order_record

            # Opening Long
            total_required = trade_value + costs.total_costs
            if self.cash < total_required:
                order_record["status"] = "REJECTED"
                order_record["reason"] = f"Insufficient funds: required ₹{total_required:.2f}, available ₹{self.cash:.2f}"
                event_bus.emit(EventType.ORDER_REJECTED, order_record)
                return order_record

            self.cash -= total_required
            self.positions[symbol] = {
                "symbol": symbol,
                "side": "LONG",
                "quantity": quantity,
                "entry_price": fill_price,
                "current_price": fill_price,
                "unrealized_pnl": 0.0,
                "entry_time": now.isoformat(),
                "entry_costs": costs.total_costs,
                "stop_loss": stop_loss,
                "target": target
            }

        elif side.upper() in ["SELL", "EXIT"]:
            # Closing Long
            if pos and pos["side"] == "LONG":
                close_qty = min(pos["quantity"], quantity)
                entry_costs_for_close = round(pos.get("entry_costs", 0.0) * (close_qty / pos["quantity"]), 2)
                gross_trade_value = fill_price * close_qty

                costs = self.cost_calculator.calculate("SELL", fill_price, close_qty, timestamp=now)
                gross_pnl = (fill_price - pos["entry_price"]) * close_qty
                net_pnl = gross_pnl - costs.total_costs - entry_costs_for_close

                self.cash += (gross_trade_value - costs.total_costs)
                self.realized_pnl += net_pnl
                self.today_pnl += net_pnl

                trade_record = {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "side": "LONG",
                    "action": "SELL_TO_CLOSE",
                    "quantity": close_qty,
                    "entry_time": pos["entry_time"],
                    "exit_time": now.isoformat(),
                    "entry_price": pos["entry_price"],
                    "exit_price": fill_price,
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "total_fees": round(costs.total_costs + entry_costs_for_close, 2),
                    "slippage_cost": round(costs.slippage, 2),
                    "strategy_reason": reason,
                    "indicator_snapshot": indicator_snapshot or pos.get("indicator_snapshot", {}),
                    "cost_regime": costs.cost_regime,
                    "is_partial": (close_qty < pos["quantity"])
                }
                self.trades.append(trade_record)

                # PARTIAL POSITION RETENTION
                remaining_qty = pos["quantity"] - close_qty
                if remaining_qty > 0:
                    pos["quantity"] = remaining_qty
                    pos["entry_costs"] = max(0.0, round(pos.get("entry_costs", 0.0) - entry_costs_for_close, 2))
                    pos["unrealized_pnl"] = round((pos["current_price"] - pos["entry_price"]) * remaining_qty, 2)
                else:
                    del self.positions[symbol]

                event_bus.emit(EventType.ORDER_FILLED, trade_record)
                return order_record

            # Opening Short - Protected by allow_shorting flag
            if not self.allow_shorting:
                order_record["status"] = "REJECTED"
                order_record["reason"] = (
                    "Short selling rejected: allow_shorting is disabled. "
                    "In Indian equity markets, overnight cash shorting is forbidden."
                )
                event_bus.emit(EventType.ORDER_REJECTED, order_record)
                return order_record

            collateral_needed = fill_price * quantity
            total_required = collateral_needed + costs.total_costs

            if self.cash < total_required:
                order_record["status"] = "REJECTED"
                order_record["reason"] = f"Insufficient funds for short collateral: required ₹{total_required:.2f}, available ₹{self.cash:.2f}"
                event_bus.emit(EventType.ORDER_REJECTED, order_record)
                return order_record

            self.cash -= total_required
            self.positions[symbol] = {
                "symbol": symbol,
                "side": "SHORT",
                "quantity": quantity,
                "entry_price": fill_price,
                "current_price": fill_price,
                "unrealized_pnl": 0.0,
                "entry_time": now.isoformat(),
                "entry_costs": costs.total_costs,
                "collateral_held": collateral_needed,
                "stop_loss": stop_loss,
                "target": target
            }

        event_bus.emit(EventType.ORDER_FILLED, order_record)
        return order_record

    def cancel_order(self, order_id: str) -> bool:
        for o in self.orders:
            if o["order_id"] == order_id and o["status"] == "PENDING":
                o["status"] = "CANCELLED"
                event_bus.emit(EventType.ORDER_CANCELLED, o)
                return True
        return False
