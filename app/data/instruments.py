"""
Indian Market Instruments Catalog and Metadata Validator.
Supports NSE Equities, Indices, and Derivatives contract specifications.
"""
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class Instrument(BaseModel):
    symbol: str
    name: str
    exchange: Literal["NSE", "BSE", "NFO", "BFO"] = "NSE"
    instrument_type: Literal["EQUITY", "INDEX", "FUTURES", "OPTIONS"] = "EQUITY"
    lot_size: int = 1
    tick_size: float = 0.05
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[Literal["CE", "PE"]] = None
    trading_hours: str = "09:15-15:30"
    is_active: bool = True
    is_demo: bool = False

    def validate_quantity(self, quantity: int) -> bool:
        """Validate if quantity is positive and a multiple of lot size."""
        if quantity <= 0:
            return False
        return (quantity % self.lot_size) == 0

    def round_to_tick(self, price: float) -> float:
        """Round price to valid instrument tick size."""
        return round(round(price / self.tick_size) * self.tick_size, 2)


# Pre-populated catalog of major Indian instruments
DEFAULT_INSTRUMENTS: Dict[str, Instrument] = {
    # Explicit Demo Instruments (Zero Live Money Risk, Synthetic Feeds)
    "NIFTY50_DEMO": Instrument(
        symbol="NIFTY50_DEMO",
        name="NIFTY 50 [DEMO SYNTHETIC]",
        exchange="NSE",
        instrument_type="INDEX",
        lot_size=25,
        tick_size=0.05,
        is_demo=True
    ),
    "RELIANCE_DEMO": Instrument(
        symbol="RELIANCE_DEMO",
        name="Reliance Industries [DEMO SYNTHETIC]",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05,
        is_demo=True
    ),
    # Major Real Indices (Live Feeds)
    "NIFTY50": Instrument(
        symbol="NIFTY50",
        name="NIFTY 50 Index",
        exchange="NSE",
        instrument_type="INDEX",
        lot_size=25,
        tick_size=0.05
    ),
    "BANKNIFTY": Instrument(
        symbol="BANKNIFTY",
        name="NIFTY Bank Index",
        exchange="NSE",
        instrument_type="INDEX",
        lot_size=15,
        tick_size=0.05
    ),
    "SENSEX": Instrument(
        symbol="SENSEX",
        name="BSE Sensex Index",
        exchange="BSE",
        instrument_type="INDEX",
        lot_size=10,
        tick_size=0.05
    ),
    # Bluechip NSE Equities (Equity lot size = 1)
    "RELIANCE": Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "TCS": Instrument(
        symbol="TCS",
        name="Tata Consultancy Services Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "HDFCBANK": Instrument(
        symbol="HDFCBANK",
        name="HDFC Bank Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "INFY": Instrument(
        symbol="INFY",
        name="Infosys Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "ICICIBANK": Instrument(
        symbol="ICICIBANK",
        name="ICICI Bank Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "TATAMOTORS": Instrument(
        symbol="TATAMOTORS",
        name="Tata Motors Ltd",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
    "SBIN": Instrument(
        symbol="SBIN",
        name="State Bank of India",
        exchange="NSE",
        instrument_type="EQUITY",
        lot_size=1,
        tick_size=0.05
    ),
}


class InstrumentRegistry:
    """Registry maintaining active instruments and metadata."""
    def __init__(self):
        self._instruments: Dict[str, Instrument] = dict(DEFAULT_INSTRUMENTS)

    def get(self, symbol: str) -> Optional[Instrument]:
        return self._instruments.get(symbol.upper())

    def list_all(self) -> List[Instrument]:
        return list(self._instruments.values())

    def list_demo(self) -> List[Instrument]:
        return [inst for inst in self._instruments.values() if inst.is_demo]

    def list_real(self) -> List[Instrument]:
        return [inst for inst in self._instruments.values() if not inst.is_demo]

    def register(self, instrument: Instrument) -> None:
        self._instruments[instrument.symbol.upper()] = instrument

    def exists(self, symbol: str) -> bool:
        return symbol.upper() in self._instruments


instrument_registry = InstrumentRegistry()
