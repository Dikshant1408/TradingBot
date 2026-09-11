"""
Base Broker Interface and Execution Boundary.
Enforces strict decoupling between strategies, paper trading, and live execution.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseBroker(ABC):
    """
    Abstract interface implemented by all execution adapters (Paper, Backtest, Live).
    """

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """True if connected to real exchange capital, False otherwise."""
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Fetch cash, margin, and equity balances."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch current open positions."""
        pass

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Fetch recent order states."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch latest market quote/price."""
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        quantity: int,
        order_type: str = "MARKET",  # MARKET or LIMIT
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Submit order for execution."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open/pending order."""
        pass
