"""
Backtest Broker Simulator with Explicit Double-Entry Ledger Accounting.
Simulates realistic trade fills, partial position executions, slippage, and statutory Indian taxes.
Guarantees cash conservation, explicit collateral accounting, and safeguards against unintended shorting.
"""
import uuid
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from app.backtesting.indian_costs import IndianCostCalculator, TradeCostBreakdown
from app.core.order_state import OrderIntent

logger = logging.getLogger("trading_bot.backtesting.broker")


class BacktestBrokerSimulator:
    """
    Simulated broker engine for backtesting with formal ledger balance accounting.
    Enforces cash conservation, proportional entry-cost adjustments on partial sales,
    explicit margin/collateral tracking for shorts, and Indian equity cash-market safety guards.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        cost_calculator: Optional[IndianCostCalculator] = None,
        allow_shorting: bool = False
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.cost_calculator = cost_calculator or IndianCostCalculator()
        self.allow_shorting = allow_shorting

        # Active positions: symbol -> dict(side, quantity, entry_price, entry_time, entry_costs, collateral_held, trade_id)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.equity_history: List[Dict[str, Any]] = []

    def get_portfolio_equity(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total liquidation equity via an explicit balance sheet ledger:
        Equity = Liquid Free Cash + Long Asset Market Value + Short Collateral Released +/- Short Unrealized PnL.
        """
        invested_value = 0.0
        for sym, pos in self.positions.items():
            curr_px = current_prices.get(sym, pos["entry_price"])
            if pos["side"] == "LONG":
                invested_value += curr_px * pos["quantity"]
            else:  # SHORT
                collateral = pos.get("collateral_held", pos["entry_price"] * pos["quantity"])
                unrealized_pnl = (pos["entry_price"] - curr_px) * pos["quantity"]
                invested_value += (collateral + unrealized_pnl)

        return round(self.cash + invested_value, 2)

    def execute_order(
        self,
        symbol: str,
        side: str,  # "BUY", "SELL", "EXIT"
        quantity: int,
        price: float,
        timestamp: datetime,
        intent: Optional[Union[str, OrderIntent]] = None,
        reason: str = "",
        indicator_snapshot: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate an order fill at execution price with slippage and Indian statutory taxes.
        Supports partial position closes, explicit order intent, and ledger accounting.
        """
        if quantity <= 0 or price <= 0:
            return None

        # Determine normalized intent
        intent_str = str(intent.value if isinstance(intent, OrderIntent) else (intent or "")).upper()
        side_upper = side.upper()

        pos = self.positions.get(symbol)

        # Disentangle order intent from simple BUY/SELL strings
        if not intent_str:
            if side_upper == "EXIT":
                intent_str = "SELL_TO_CLOSE" if (pos and pos["side"] == "LONG") else "BUY_TO_CLOSE"
            elif side_upper == "BUY":
                intent_str = "BUY_TO_CLOSE" if (pos and pos["side"] == "SHORT") else "BUY_TO_OPEN"
            elif side_upper == "SELL":
                intent_str = "SELL_TO_CLOSE" if (pos and pos["side"] == "LONG") else "SELL_TO_OPEN"

        # Apply slippage
        slippage_factor = self.cost_calculator.slippage_pct
        is_buy_side = intent_str in ["BUY_TO_OPEN", "BUY_TO_CLOSE"] or side_upper == "BUY"
        if is_buy_side:
            fill_price = round(price * (1.0 + slippage_factor), 2)
            cost_side = "BUY"
        else:
            fill_price = round(price * (1.0 - slippage_factor), 2)
            cost_side = "SELL"

        trade_id = str(uuid.uuid4())

        # =========================================================================
        # 1. LIQUIDATE / REDUCE LONG POSITION (SELL_TO_CLOSE)
        # =========================================================================
        if intent_str == "SELL_TO_CLOSE" or (side_upper in ["SELL", "EXIT"] and pos and pos["side"] == "LONG"):
            if not pos or pos["side"] != "LONG":
                logger.warning(f"Ignored SELL_TO_CLOSE for {symbol}: No active LONG position.")
                return None

            close_qty = min(pos["quantity"], quantity)
            if close_qty <= 0:
                return None

            # Calculate proportional entry fees attributable to this portion
            entry_costs_for_close = round(pos.get("entry_costs", 0.0) * (close_qty / pos["quantity"]), 2)

            costs: TradeCostBreakdown = self.cost_calculator.calculate(
                side="SELL",
                price=fill_price,
                quantity=close_qty,
                timestamp=timestamp
            )

            gross_trade_value = fill_price * close_qty
            gross_pnl = (fill_price - pos["entry_price"]) * close_qty
            net_pnl = gross_pnl - costs.total_costs - entry_costs_for_close

            # Release cash from sale back to liquid reserves (minus exit statutory taxes)
            self.cash += (gross_trade_value - costs.total_costs)

            trade_record = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": "LONG",
                "action": "SELL_TO_CLOSE",
                "quantity": close_qty,
                "entry_time": pos["entry_time"],
                "exit_time": timestamp,
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
            self.closed_trades.append(trade_record)

            # PARTIAL POSITION BUG FIX: Retain remaining position if not fully closed
            remaining_qty = pos["quantity"] - close_qty
            if remaining_qty > 0:
                pos["quantity"] = remaining_qty
                pos["entry_costs"] = max(0.0, round(pos.get("entry_costs", 0.0) - entry_costs_for_close, 2))
            else:
                del self.positions[symbol]

            return trade_record

        # =========================================================================
        # 2. COVER / REDUCE SHORT POSITION (BUY_TO_CLOSE)
        # =========================================================================
        elif intent_str == "BUY_TO_CLOSE" or (side_upper in ["BUY", "EXIT"] and pos and pos["side"] == "SHORT"):
            if not pos or pos["side"] != "SHORT":
                logger.warning(f"Ignored BUY_TO_CLOSE for {symbol}: No active SHORT position.")
                return None

            close_qty = min(pos["quantity"], quantity)
            if close_qty <= 0:
                return None

            entry_costs_for_close = round(pos.get("entry_costs", 0.0) * (close_qty / pos["quantity"]), 2)
            proportional_collateral = round(pos.get("collateral_held", pos["entry_price"] * pos["quantity"]) * (close_qty / pos["quantity"]), 2)

            costs = self.cost_calculator.calculate(
                side="BUY",
                price=fill_price,
                quantity=close_qty,
                timestamp=timestamp
            )

            gross_pnl = (pos["entry_price"] - fill_price) * close_qty
            net_pnl = gross_pnl - costs.total_costs - entry_costs_for_close

            # Release reserved collateral + PnL - exit taxes
            self.cash += (proportional_collateral + gross_pnl - costs.total_costs)

            trade_record = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": "SHORT",
                "action": "BUY_TO_CLOSE",
                "quantity": close_qty,
                "entry_time": pos["entry_time"],
                "exit_time": timestamp,
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
            self.closed_trades.append(trade_record)

            # PARTIAL POSITION BUG FIX: Retain remaining short position if not fully closed
            remaining_qty = pos["quantity"] - close_qty
            if remaining_qty > 0:
                pos["quantity"] = remaining_qty
                pos["collateral_held"] = max(0.0, round(pos.get("collateral_held", 0.0) - proportional_collateral, 2))
                pos["entry_costs"] = max(0.0, round(pos.get("entry_costs", 0.0) - entry_costs_for_close, 2))
            else:
                del self.positions[symbol]

            return trade_record

        # =========================================================================
        # 3. OPEN OR ADD TO LONG POSITION (BUY_TO_OPEN)
        # =========================================================================
        elif intent_str == "BUY_TO_OPEN" or side_upper == "BUY":
            costs = self.cost_calculator.calculate(
                side="BUY",
                price=fill_price,
                quantity=quantity,
                timestamp=timestamp
            )
            total_required = (fill_price * quantity) + costs.total_costs

            if self.cash < total_required:
                max_qty = int(self.cash / (fill_price * (1.0 + 0.001)))
                if max_qty <= 0:
                    logger.warning(f"Insufficient cash (₹{self.cash:.2f}) to open LONG {quantity} {symbol}")
                    return None
                quantity = max_qty
                costs = self.cost_calculator.calculate(
                    side="BUY",
                    price=fill_price,
                    quantity=quantity,
                    timestamp=timestamp
                )
                total_required = (fill_price * quantity) + costs.total_costs

            self.cash -= total_required

            # If position already exists, update weighted average entry
            if pos and pos["side"] == "LONG":
                total_qty = pos["quantity"] + quantity
                avg_entry = round(((pos["entry_price"] * pos["quantity"]) + (fill_price * quantity)) / total_qty, 2)
                pos["quantity"] = total_qty
                pos["entry_price"] = avg_entry
                pos["entry_costs"] += costs.total_costs
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "side": "LONG",
                    "quantity": quantity,
                    "entry_price": fill_price,
                    "entry_time": timestamp,
                    "entry_costs": costs.total_costs,
                    "indicator_snapshot": indicator_snapshot or {},
                    "trade_id": trade_id
                }

            return {
                "trade_id": trade_id,
                "action": "BUY_TO_OPEN",
                "fill_price": fill_price,
                "quantity": quantity,
                "costs": costs.model_dump()
            }

        # =========================================================================
        # 4. OPEN OR ADD TO SHORT POSITION (SELL_TO_OPEN)
        # =========================================================================
        elif intent_str == "SELL_TO_OPEN" or side_upper == "SELL":
            # Safety gate: reject short selling if not explicitly enabled
            if not self.allow_shorting:
                logger.info(
                    f"Short order rejected for {symbol}: allow_shorting=False. "
                    "In Indian equity markets, overnight cash shorting is forbidden."
                )
                return None

            costs = self.cost_calculator.calculate(
                side="SELL",
                price=fill_price,
                quantity=quantity,
                timestamp=timestamp
            )

            # Explicit collateral requirement: 100% of notional trade value reserved from cash
            collateral_needed = (fill_price * quantity)
            total_required = collateral_needed + costs.total_costs

            if self.cash < total_required:
                max_qty = int(self.cash / (fill_price * (1.0 + 0.001)))
                if max_qty <= 0:
                    logger.warning(f"Insufficient cash for short collateral (₹{self.cash:.2f}) on {quantity} {symbol}")
                    return None
                quantity = max_qty
                costs = self.cost_calculator.calculate(
                    side="SELL",
                    price=fill_price,
                    quantity=quantity,
                    timestamp=timestamp
                )
                collateral_needed = fill_price * quantity
                total_required = collateral_needed + costs.total_costs

            # Deduct collateral and fees from liquid cash
            self.cash -= total_required

            if pos and pos["side"] == "SHORT":
                total_qty = pos["quantity"] + quantity
                avg_entry = round(((pos["entry_price"] * pos["quantity"]) + (fill_price * quantity)) / total_qty, 2)
                pos["quantity"] = total_qty
                pos["entry_price"] = avg_entry
                pos["collateral_held"] += collateral_needed
                pos["entry_costs"] += costs.total_costs
            else:
                self.positions[symbol] = {
                    "symbol": symbol,
                    "side": "SHORT",
                    "quantity": quantity,
                    "entry_price": fill_price,
                    "entry_time": timestamp,
                    "entry_costs": costs.total_costs,
                    "collateral_held": collateral_needed,
                    "indicator_snapshot": indicator_snapshot or {},
                    "trade_id": trade_id
                }

            return {
                "trade_id": trade_id,
                "action": "SELL_TO_OPEN",
                "fill_price": fill_price,
                "quantity": quantity,
                "costs": costs.model_dump()
            }

        return None
