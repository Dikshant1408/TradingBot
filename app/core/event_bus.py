"""
Lightweight asynchronous event dispatcher for trading bot events.
"""
import asyncio
import logging
from typing import Callable, Dict, List, Any
from enum import Enum

logger = logging.getLogger("trading_bot.event_bus")


class EventType(str, Enum):
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    POSITION_UPDATED = "POSITION_UPDATED"
    PORTFOLIO_UPDATED = "PORTFOLIO_UPDATED"
    RISK_ALERT = "RISK_ALERT"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    STATUS_CHANGED = "STATUS_CHANGED"


class EventBus:
    """
    Central event dispatcher decoupling strategies, execution engines,
    risk management, and websocket notifications.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def emit_async(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to all registered async and sync subscribers."""
        if event_type not in self._subscribers:
            return

        handlers = list(self._subscribers[event_type])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error executing event handler for {event_type}: {e}", exc_info=True)

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Synchronous dispatch or scheduled on running loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit_async(event_type, data))
        except RuntimeError:
            # No running loop, call synchronously where possible
            if event_type in self._subscribers:
                for handler in self._subscribers[event_type]:
                    try:
                        if not asyncio.iscoroutinefunction(handler):
                            handler(data)
                    except Exception as e:
                        logger.error(f"Sync error executing handler for {event_type}: {e}")


# Global EventBus singleton
event_bus = EventBus()
