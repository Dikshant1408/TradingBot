"""
Indian Market Clock, Timezone conversions and Trading Session calendar.
Internally UTC, UI and market session calculations in Asia/Kolkata (IST).
"""
from datetime import datetime, time, date
import pytz
from typing import Tuple

IST_TIMEZONE = pytz.timezone("Asia/Kolkata")
UTC_TIMEZONE = pytz.UTC

# Standard NSE / BSE Trading Hours
MARKET_OPEN_TIME = time(9, 15)   # 09:15 AM IST
MARKET_CLOSE_TIME = time(15, 30)  # 03:30 PM IST

# Known NSE / BSE Trading Holidays (YYYY-MM-DD)
INDIAN_MARKET_HOLIDAYS = {
    # 2024
    "2024-01-26", "2024-03-08", "2024-03-25", "2024-04-11", "2024-04-17",
    "2024-05-01", "2024-06-17", "2024-07-17", "2024-08-15", "2024-10-02",
    "2024-11-01", "2024-11-15", "2024-12-25",
    # 2025
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10",
    "2025-04-14", "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27",
    "2025-10-02", "2025-10-21", "2025-10-22", "2025-11-05", "2025-12-25",
    # 2026
    "2026-01-26", "2026-03-03", "2026-03-20", "2026-04-03", "2026-04-14",
    "2026-05-01", "2026-08-15", "2026-10-02", "2026-10-20", "2026-11-09",
    "2026-12-25"
}


def get_utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC_TIMEZONE)


def get_ist_now() -> datetime:
    """Return timezone-aware current IST datetime."""
    return datetime.now(IST_TIMEZONE)


def utc_to_ist(dt: datetime) -> datetime:
    """Convert any datetime to timezone-aware IST datetime."""
    if dt.tzinfo is None:
        dt = UTC_TIMEZONE.localize(dt)
    return dt.astimezone(IST_TIMEZONE)


def ist_to_utc(dt: datetime) -> datetime:
    """Convert any datetime to timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        dt = IST_TIMEZONE.localize(dt)
    return dt.astimezone(UTC_TIMEZONE)


def format_ist(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S IST") -> str:
    """Format datetime as IST string for terminal display."""
    return utc_to_ist(dt).strftime(fmt)


def is_market_day(target_date: date) -> bool:
    """
    Check if a given date is an Indian market trading day (Monday-Friday, not a holiday).
    """
    if target_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    date_str = target_date.strftime("%Y-%m-%d")
    return date_str not in INDIAN_MARKET_HOLIDAYS


def is_market_open_now(allow_weekend: bool = False) -> Tuple[bool, str]:
    """
    Check if Indian markets are currently open for regular trading (09:15 to 15:30 IST).
    Returns (is_open, status_message).
    """
    now_ist = get_ist_now()
    current_date = now_ist.date()
    current_time = now_ist.time()

    if not allow_weekend and not is_market_day(current_date):
        if now_ist.weekday() >= 5:
            return False, "Market is closed (Weekend)"
        return False, "Market is closed (Exchange Holiday)"

    if current_time < MARKET_OPEN_TIME:
        return False, f"Market is closed (Pre-market / Opens at 09:15 IST, current time: {current_time.strftime('%H:%M')})"
    if current_time > MARKET_CLOSE_TIME:
        return False, f"Market is closed (Session ended at 15:30 IST, current time: {current_time.strftime('%H:%M')})"

    return True, "Market is open for regular trading"
