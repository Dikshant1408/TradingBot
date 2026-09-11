"""
Telegram Notification Client.
Asynchronously sends critical trading alerts: Signals, Trade Executions, Risk Halts, and Emergency Stops.
"""
import logging
import asyncio
from typing import Optional
import requests
from app.config.settings import get_settings

logger = logging.getLogger("trading_bot.notifications.telegram")
settings = get_settings()


class TelegramNotifier:
    """
    Sends structured alerts to a private Telegram channel/chat.
    Safe failure: never crashes or blocks trading if network fails.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = enabled if enabled is not None else settings.TELEGRAM_ENABLED

    def send_message(self, text: str) -> bool:
        """Send message synchronously in a background thread."""
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                return True
            logger.warning(f"Telegram alert failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Failed to deliver Telegram notification: {e}")
        return False

    async def send_message_async(self, text: str) -> bool:
        """Send message asynchronously without blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.send_message, text)

    def notify_bot_started(self, mode: str, strategy: str, symbol: str) -> None:
        msg = (
            f"<b>🟢 TRADING BOT STARTED</b>\n\n"
            f"<b>Mode:</b> {mode.upper()}\n"
            f"<b>Strategy:</b> {strategy}\n"
            f"<b>Instrument:</b> {symbol}\n"
            f"<b>Host:</b> Localhost"
        )
        self.send_message(msg)

    def notify_signal(self, action: str, symbol: str, price: float, reason: str) -> None:
        emoji = "🟢" if action == "BUY" else "🔴"
        msg = (
            f"<b>{emoji} SIGNAL GENERATED</b>\n\n"
            f"<b>Action:</b> {action}\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Price:</b> ₹{price:.2f}\n"
            f"<b>Reason:</b> {reason}"
        )
        self.send_message(msg)

    def notify_trade(self, action: str, symbol: str, quantity: int, price: float, pnl: Optional[float] = None) -> None:
        pnl_text = f"\n<b>Net P&L:</b> ₹{pnl:.2f}" if pnl is not None else ""
        msg = (
            f"<b>⚡ TRADE EXECUTED</b>\n\n"
            f"<b>Action:</b> {action}\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Price:</b> ₹{price:.2f}{pnl_text}"
        )
        self.send_message(msg)

    def notify_risk_halt(self, reason: str) -> None:
        msg = (
            f"<b>🚨 TRADING HALTED - RISK LIMIT BREACHED</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<i>Execution blocked automatically.</i>"
        )
        self.send_message(msg)

    def notify_emergency_stop(self, reason: str) -> None:
        msg = (
            f"<b>🛑 EMERGENCY STOP ACTIVATED</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<i>Manual restart required to resume operations.</i>"
        )
        self.send_message(msg)


# Global notifier singleton
telegram_notifier = TelegramNotifier()
