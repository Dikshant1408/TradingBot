"""
Backtest Broker Simulator.
Simulates realistic trade fills, position matching, cash balances, and Indian market costs.
"""
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.backtesting.indian_costs import IndianCostCalculator, TradeCostBreakdown

logger = logging.getLogger("trading_bot.backtesting.broker")


class BacktestBrokerSimulator:
    """
    Simulated broker engine for backtesting.
    Enforces cash accounting, position tracking, slippage, and statutory taxes.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        cost_calculator: Optional[IndianCostCalculator] = None
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.cost_calculator = cost_calculator or IndianCostCalculator()

        # Active positions: symbol -> dict(side, quantity, entry_price, entry_time, trade_id)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.equity_history: List[Dict[str, Any]] = []

    def get_portfolio_equity(self, current_prices: Dict[str, float]) -> float:
        """Calculate total liquidation equity (cash + market value of open positions)."""
        invested_value = 0.0
        for sym, pos in self.positions.items():
            curr_px = current_prices.get(sym, pos["entry_price"])
            if pos["side"] == "LONG":
                invested_value += curr_px * pos["quantity"]
            else:  # SHORT
                # PnL for short: (entry - curr) * qty
                invested_value += (2 * pos["entry_price"] - curr_px) * pos["quantity"]
        return round(self.cash + invested_value, 2)

    def execute_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        quantity: int,
        price: float,
        timestamp: datetime,
        reason: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate an order fill at bar execution price with slippage and Indian taxes.
        """
        if quantity <= 0 or price <= 0:
            return None

        # Slippage adjustment
        slippage_factor = self.cost_calculator.slippage_pct
        if side.upper() == "BUY":
            fill_price = round(price * (1.0 + slippage_factor), 2)
        else:
            fill_price = round(price * (1.0 - slippage_factor), 2)

        # Statutory taxes and brokerage
        costs: TradeCostBreakdown = self.cost_calculator.calculate(
            side=side,
            price=fill_price,
            quantity=quantity
        )

        total_trade_value = fill_price * quantity
        trade_id = str(uuid.uuid4())

        # Check existing position
        pos = self.positions.get(symbol)

        if side.upper() == "BUY":
            # If closing a short position
            if pos and pos["side"] == "SHORT":
                close_qty = min(pos["quantity"], quantity)
                gross_pnl = (pos["entry_price"] - fill_price) * close_qty
                net_pnl = gross_pnl - costs.total_costs - pos.get("entry_costs", 0)

                self.cash += (pos["entry_price"] * close_qty) + gross_pnl - costs.total_costs
                trade_record = {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": "SHORT",
                    "quantity": close_qty,
                    "entry_time": pos["entry_time"],
                    "exit_time": timestamp,
                    "entry_price": pos["entry_price"],
                    "exit_price": fill_price,
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "total_fees": round(costs.total_costs + pos.get("entry_costs", 0), 2),
                    "slippage_cost": round(costs.slippage, 2),
                    "strategy_reason": reason
                }
                self.closed_trades.append(trade_record)
                del self.positions[symbol]
                return trade_record

            # Opening or adding to LONG position
            required_cash = total_trade_value + costs.total_costs
            if self.cash < required_cash:
                # Can't afford full quantity, adjust if partial
                max_qty = int(self.cash / (fill_price * (1 + 0.001)))
                if max_qty <= 0:
                    logger.warning(f"Insufficient cash (₹{self.cash:.2f}) for order of {quantity} {symbol}")
                    return None
                quantity = max_qty
                total_trade_value = fill_price * quantity
                costs = self.cost_calculator.calculate(side, fill_price, quantity)

            self.cash -= (total_trade_value + costs.total_costs)
            self.positions[symbol] = {
                "side": "LONG",
                "quantity": quantity,
                "entry_price": fill_price,
                "entry_time": timestamp,
                "entry_costs": costs.total_costs,
                "trade_id": trade_id
            }
            return {
                "trade_id": trade_id,
                "action": "OPEN_LONG",
                "fill_price": fill_price,
                "quantity": quantity,
                "costs": costs.model_dump()
            }

        elif side.upper() in ["SELL", "EXIT"]:
            # Closing a LONG position
            if pos and pos["side"] == "LONG":
                close_qty = min(pos["quantity"], quantity)
                gross_pnl = (fill_price - pos["entry_price"]) * close_qty
                net_pnl = gross_pnl - costs.total_costs - pos.get("entry_costs", 0)

                self.cash += (total_trade_value - costs.total_costs)
                trade_record = {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": "LONG",
                    "quantity": close_qty,
                    "entry_time": pos["entry_time"],
                    "exit_time": timestamp,
                    "entry_price": pos["entry_price"],
                    "exit_price": fill_price,
                    "gross_pnl": round(gross_pnl, 2),
                    "net_pnl": round(net_pnl, 2),
                    "total_fees": round(costs.total_costs + pos.get("entry_costs", 0), 2),
                    "slippage_cost": round(costs.slippage, 2),
                    "strategy_reason": reason
                }
                self.closed_trades.append(trade_record)
                del self.positions[symbol]
                return trade_record

            # Opening SHORT position
            self.cash -= costs.total_costs
            self.positions[symbol] = {
                "side": "SHORT",
                "quantity": quantity,
                "entry_price": fill_price,
                "entry_time": timestamp,
                "entry_costs": costs.total_costs,
                "trade_id": trade_id
            }
            return {
                "trade_id": trade_id,
                "action": "OPEN_SHORT",
                "fill_price": fill_price,
                "quantity": quantity,
                "costs": costs.model_dump()
            }

        return None
