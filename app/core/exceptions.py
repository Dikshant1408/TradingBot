"""
Core trading engine domain exceptions.
"""


class TradingBotError(Exception):
    """Base exception for all trading bot errors."""
    pass


class RiskViolationError(TradingBotError):
    """Raised when a risk limit is breached (daily loss, max drawdown, etc.)."""
    pass


class KillSwitchActiveError(TradingBotError):
    """Raised when an execution is attempted while the kill switch is engaged."""
    pass


class EmergencyStopActiveError(TradingBotError):
    """Raised when an execution is attempted while emergency stop is triggered."""
    pass


class DuplicateOrderError(TradingBotError):
    """Raised when a duplicate order or signal is detected within the safety window."""
    pass


class MarketClosedError(TradingBotError):
    """Raised when order execution is attempted outside Indian market hours."""
    pass


class InstrumentNotFoundError(TradingBotError):
    """Raised when an invalid or unknown instrument symbol is requested."""
    pass


class LiveTradingBlockedError(TradingBotError):
    """Raised when live trading pre-flight check fails or authorization is missing."""
    pass


class DataValidationError(TradingBotError):
    """Raised when market data fails integrity checks (negative prices, inverted high/low, etc.)."""
    pass
