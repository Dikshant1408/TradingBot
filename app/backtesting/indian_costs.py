"""
Indian Market Statutory Transaction Cost & Tax Calculator.
Models Brokerage, STT, Exchange Turnover Charges, GST, SEBI Turnover, and Stamp Duty.
"""
from typing import Dict
from pydantic import BaseModel, Field


class TradeCostBreakdown(BaseModel):
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    gst: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_costs: float = 0.0


class IndianCostCalculator:
    """
    Computes exact regulatory & exchange transaction costs for Indian equities and derivatives.
    Default rates match current NSE equity intraday rules:
    - Brokerage: min(0.03%, ₹20) or flat ₹20
    - STT: 0.025% on SELL only for intraday
    - Exchange Turnover Charge: 0.00297% (NSE)
    - GST: 18% on (Brokerage + Exchange Charges + SEBI charges)
    - SEBI Turnover: ₹10 per crore (0.0001%)
    - Stamp Duty: 0.003% on BUY only for intraday
    """

    def __init__(
        self,
        brokerage_per_order: float = 20.0,
        stt_rate: float = 0.00025,
        exchange_rate: float = 0.0000297,
        gst_rate: float = 0.18,
        sebi_rate: float = 0.000001,
        stamp_duty_rate: float = 0.00003,
        slippage_pct: float = 0.0005
    ):
        self.brokerage_per_order = brokerage_per_order
        self.stt_rate = stt_rate
        self.exchange_rate = exchange_rate
        self.gst_rate = gst_rate
        self.sebi_rate = sebi_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage_pct = slippage_pct

    def calculate(
        self,
        side: str,  # "BUY" or "SELL"
        price: float,
        quantity: int
    ) -> TradeCostBreakdown:
        turnover = price * quantity
        if turnover <= 0:
            return TradeCostBreakdown()

        # 1. Brokerage (e.g. flat ₹20 or min(₹20, 0.03%))
        brokerage = min(self.brokerage_per_order, turnover * 0.0003)

        # 2. STT (Securities Transaction Tax) - for intraday equity, charged on SELL
        stt = (turnover * self.stt_rate) if side.upper() == "SELL" else 0.0

        # 3. Exchange Turnover Charges
        exchange_charges = turnover * self.exchange_rate

        # 4. SEBI Turnover Charges
        sebi_charges = turnover * self.sebi_rate

        # 5. GST (18% on Brokerage + Exchange + SEBI)
        gst = (brokerage + exchange_charges + sebi_charges) * self.gst_rate

        # 6. Stamp Duty - charged on BUY only
        stamp_duty = (turnover * self.stamp_duty_rate) if side.upper() == "BUY" else 0.0

        # 7. Slippage cost (market impact)
        slippage = turnover * self.slippage_pct

        total = round(brokerage + stt + exchange_charges + gst + sebi_charges + stamp_duty + slippage, 2)

        return TradeCostBreakdown(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            gst=round(gst, 2),
            sebi_charges=round(sebi_charges, 4),
            stamp_duty=round(stamp_duty, 2),
            slippage=round(slippage, 2),
            total_costs=total
        )
