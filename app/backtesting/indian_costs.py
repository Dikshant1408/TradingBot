"""
Date-Aware Indian Market Statutory Transaction Cost & Tax Calculator.
Supports Equity Intraday, Equity Delivery, Futures, and Options across regulatory regimes
(including Union Budget 2024 STT hikes effective Oct 1, 2024).
"""
from typing import Optional, Literal, Union
from enum import Enum
from datetime import datetime, date
from pydantic import BaseModel, Field


class MarketSegment(str, Enum):
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    EQUITY_DELIVERY = "EQUITY_DELIVERY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"


class BrokerProfile(str, Enum):
    """
    Explicit broker cost profiles with distinct tariff structures.
    """
    ZERODHA = "ZERODHA"                # Zerodha: Free delivery, min(₹20, 0.03%) intraday, ₹20 F&O
    ICICI_DIRECT = "ICICI_DIRECT"      # ICICI Direct Neo: Free delivery, ₹20 flat intraday & F&O
    FLAT_DISCOUNT = "FLAT_DISCOUNT"    # Generic discount broker: Flat ₹20 per executed order
    PERCENTAGE = "PERCENTAGE"          # Pure percentage-based brokerage (e.g. 0.05%)
    ZERO = "ZERO"                      # Zero brokerage (for isolating statutory taxes)
    CUSTOM = "CUSTOM"                  # Custom user-defined limits


class TradeCostBreakdown(BaseModel):
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_costs: float = 0.0
    cost_regime: str = "DEFAULT"
    broker_profile: str = "ZERODHA"
    is_indicative: bool = True  # Estimated indicative figures subject to broker round-off


class IndianCostCalculator:
    """
    Computes estimated statutory transaction costs, taxes, and broker commissions.
    Notice: All values are Estimated Statutory Taxes & Brokerage (Indicative).
    """

    OCT_2024_BUDGET_DATE = date(2024, 10, 1)

    def __init__(
        self,
        brokerage_per_order: float = 20.0,
        segment: Literal["EQUITY_INTRADAY", "EQUITY_DELIVERY", "FUTURES", "OPTIONS"] = "EQUITY_INTRADAY",
        slippage_pct: float = 0.0005,
        gst_rate: float = 0.18,
        sebi_rate: float = 0.000001,
        broker_profile: BrokerProfile = BrokerProfile.ZERODHA,
        brokerage_pct: float = 0.0003
    ):
        self.brokerage_per_order = brokerage_per_order
        self.segment = segment
        self.slippage_pct = slippage_pct
        self.gst_rate = gst_rate
        self.sebi_rate = sebi_rate
        self.broker_profile = broker_profile if isinstance(broker_profile, BrokerProfile) else BrokerProfile(str(broker_profile).upper())
        self.brokerage_pct = brokerage_pct

    def get_stt_rate(self, side: str, trade_date: Optional[date] = None) -> float:
        """
        Return applicable STT rate based on instrument segment, order side, and regulatory date.
        """
        side_upper = side.upper()
        is_post_oct_2024 = (trade_date >= self.OCT_2024_BUDGET_DATE) if trade_date else True

        if self.segment == "EQUITY_INTRADAY":
            # 0.025% on SELL only
            return 0.00025 if side_upper == "SELL" else 0.0

        elif self.segment == "EQUITY_DELIVERY":
            # 0.1% on BOTH BUY and SELL
            return 0.001

        elif self.segment == "FUTURES":
            # Post Oct 1, 2024: 0.02% on SELL. Prior: 0.0125% on SELL.
            if side_upper == "SELL":
                return 0.00020 if is_post_oct_2024 else 0.000125
            return 0.0

        elif self.segment == "OPTIONS":
            # Post Oct 1, 2024: 0.1% on SELL premium. Prior: 0.0625% on SELL premium.
            if side_upper == "SELL":
                return 0.0010 if is_post_oct_2024 else 0.000625
            return 0.0

        return 0.0

    def get_stamp_duty_rate(self, side: str) -> float:
        """Stamp duty is charged on BUY only."""
        if side.upper() != "BUY":
            return 0.0

        if self.segment == "EQUITY_INTRADAY":
            return 0.00003  # 0.003%
        elif self.segment == "EQUITY_DELIVERY":
            return 0.00015  # 0.015%
        elif self.segment == "FUTURES":
            return 0.00002  # 0.002%
        elif self.segment == "OPTIONS":
            return 0.00003  # 0.003%
        return 0.00003

    def get_exchange_charge_rate(self) -> float:
        if self.segment in ["EQUITY_INTRADAY", "EQUITY_DELIVERY"]:
            return 0.0000297  # NSE Cash ~0.00297%
        elif self.segment == "FUTURES":
            return 0.0000173  # NSE Futures ~0.00173%
        elif self.segment == "OPTIONS":
            return 0.0003503  # NSE Options ~0.03503%
        return 0.0000297

    def calculate_brokerage(self, turnover: float, segment: Optional[str] = None) -> float:
        """
        Calculate brokerage according to explicit broker profile tariff rules.
        """
        seg = segment or self.segment
        profile = self.broker_profile

        if profile == BrokerProfile.ZERODHA:
            if seg == "EQUITY_DELIVERY":
                return 0.0  # Free equity delivery
            elif seg == "EQUITY_INTRADAY":
                return min(self.brokerage_per_order, turnover * 0.0003)
            elif seg in ["FUTURES", "OPTIONS"]:
                return self.brokerage_per_order
            return min(self.brokerage_per_order, turnover * 0.0003)

        elif profile == BrokerProfile.ICICI_DIRECT:
            if seg == "EQUITY_DELIVERY":
                return 0.0
            elif seg in ["EQUITY_INTRADAY", "FUTURES", "OPTIONS"]:
                return min(self.brokerage_per_order, turnover * 0.0005)
            return self.brokerage_per_order

        elif profile == BrokerProfile.FLAT_DISCOUNT:
            return self.brokerage_per_order

        elif profile == BrokerProfile.PERCENTAGE:
            return turnover * self.brokerage_pct

        elif profile == BrokerProfile.ZERO:
            return 0.0

        elif profile == BrokerProfile.CUSTOM:
            if self.brokerage_pct > 0:
                return min(self.brokerage_per_order, turnover * self.brokerage_pct)
            return self.brokerage_per_order

        return min(self.brokerage_per_order, turnover * 0.0003)

    def calculate(
        self,
        side: str,
        price: float,
        quantity: int,
        timestamp: Optional[Union[datetime, str, date]] = None,
        segment: Optional[Union[str, MarketSegment]] = None,
        trade_date: Optional[Union[datetime, date]] = None
    ) -> TradeCostBreakdown:
        turnover = price * quantity
        if turnover <= 0:
            return TradeCostBreakdown(broker_profile=self.broker_profile.value)

        # Allow per-calculation segment override if provided
        active_segment = str(segment.value if isinstance(segment, MarketSegment) else (segment or self.segment))
        original_segment = self.segment
        self.segment = active_segment

        # Parse trade date for regime identification
        parsed_date: Optional[date] = None
        ts = trade_date or timestamp
        if ts:
            if isinstance(ts, str):
                try:
                    parsed_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
                except Exception:
                    pass
            elif isinstance(ts, (datetime, date)):
                parsed_date = ts.date() if isinstance(ts, datetime) else ts

        regime_label = "POST_OCT_2024" if (parsed_date and parsed_date >= self.OCT_2024_BUDGET_DATE) else "PRE_OCT_2024"

        # 1. Brokerage based on explicit broker tariff model
        brokerage = self.calculate_brokerage(turnover, active_segment)

        # 2. STT
        stt_rate = self.get_stt_rate(side, parsed_date)
        stt = turnover * stt_rate

        # 3. Exchange Charges
        exchange_charges = turnover * self.get_exchange_charge_rate()

        # 4. SEBI Turnover Charges
        sebi_charges = turnover * self.sebi_rate

        # 5. GST (18% on Brokerage + Exchange + SEBI)
        gst = (brokerage + exchange_charges + sebi_charges) * self.gst_rate

        # 6. Stamp Duty
        stamp_duty = turnover * self.get_stamp_duty_rate(side)

        # 7. Slippage
        slippage = turnover * self.slippage_pct

        total = round(brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty + slippage, 2)
        cost_regime_str = f"{self.segment}_{regime_label}"
        self.segment = original_segment

        return TradeCostBreakdown(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            gst=round(gst, 2),
            sebi_charges=round(sebi_charges, 4),
            stamp_duty=round(stamp_duty, 2),
            slippage=round(slippage, 2),
            total_costs=total,
            cost_regime=cost_regime_str,
            broker_profile=self.broker_profile.value,
            is_indicative=True
        )
