"""
Market data normalizer and data integrity validation engine.
Ensures clean, chronological, zero-lookahead, valid OHLCV candles.
"""
import logging
from typing import Tuple, Optional
import pandas as pd
import numpy as np
from app.core.exceptions import DataValidationError

logger = logging.getLogger("trading_bot.data.normalizer")


class CandleNormalizer:
    """
    Cleans, validates, and standardizes raw OHLCV datasets.
    """

    COLUMN_MAP = {
        "date": "timestamp",
        "datetime": "timestamp",
        "time": "timestamp",
        "timestamp": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adj close": "close",
        "volume": "volume",
        "vol": "volume",
        "symbol": "symbol",
        "ticker": "symbol"
    }

    @classmethod
    def normalize_dataframe(
        cls,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN"
    ) -> Tuple[pd.DataFrame, dict]:
        """
        Normalize and validate a raw dataframe into standard OHLCV format.
        Returns: (cleaned_dataframe, audit_summary_dict)
        """
        if df.empty:
            raise DataValidationError("Input DataFrame is empty.")

        original_count = len(df)
        audit = {
            "original_rows": original_count,
            "dropped_invalid_prices": 0,
            "dropped_inverted_high_low": 0,
            "dropped_duplicates": 0,
            "final_rows": 0,
            "start_time": None,
            "end_time": None,
            "symbol": symbol
        }

        # 1. Map columns case-insensitively
        mapped_cols = {}
        for col in df.columns:
            clean_col = str(col).strip().lower()
            if clean_col in cls.COLUMN_MAP:
                mapped_cols[col] = cls.COLUMN_MAP[clean_col]

        df = df.rename(columns=mapped_cols)

        # Check required columns
        required = ["timestamp", "open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise DataValidationError(f"Missing mandatory OHLCV columns: {missing}. Found: {list(df.columns)}")

        # Add default volume if missing
        if "volume" not in df.columns:
            df["volume"] = 0

        # Add symbol column
        df["symbol"] = symbol.upper()

        # 2. Parse timestamps
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        except Exception as e:
            raise DataValidationError(f"Failed to parse timestamp column: {e}")

        # Drop rows with null timestamps or prices
        df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])

        # 3. Numeric conversion
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Drop any conversion NaNs
        df = df.dropna(subset=["open", "high", "low", "close"])

        # 4. Filter invalid prices (must be > 0)
        valid_price_mask = (
            (df["open"] > 0) &
            (df["high"] > 0) &
            (df["low"] > 0) &
            (df["close"] > 0) &
            (df["volume"] >= 0)
        )
        invalid_prices_count = (~valid_price_mask).sum()
        if invalid_prices_count > 0:
            audit["dropped_invalid_prices"] = int(invalid_prices_count)
            df = df[valid_price_mask]

        # 5. Sanity check: High must be >= Low, High >= max(Open, Close), Low <= min(Open, Close)
        # Small tolerance for floating point representations (1e-4)
        tol = 1e-4
        inverted_mask = (
            (df["high"] < df["low"] - tol) |
            (df["high"] < df["open"] - tol) |
            (df["high"] < df["close"] - tol) |
            (df["low"] > df["open"] + tol) |
            (df["low"] > df["close"] + tol)
        )
        inverted_count = inverted_mask.sum()
        if inverted_count > 0:
            audit["dropped_inverted_high_low"] = int(inverted_count)
            df = df[~inverted_mask]

        if df.empty:
            raise DataValidationError("All rows were filtered out due to invalid OHLC price data.")

        # 6. Deduplicate timestamps
        duplicates = df.duplicated(subset=["timestamp"], keep="last").sum()
        if duplicates > 0:
            audit["dropped_duplicates"] = int(duplicates)
            df = df.drop_duplicates(subset=["timestamp"], keep="last")

        # 7. Sort chronologically ascending
        df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)

        audit["final_rows"] = len(df)
        audit["start_time"] = df["timestamp"].iloc[0].isoformat()
        audit["end_time"] = df["timestamp"].iloc[-1].isoformat()

        # Standard column order
        df = df[["timestamp", "open", "high", "low", "close", "volume", "symbol"]]

        logger.info(
            f"Normalized {symbol}: {original_count} -> {len(df)} candles "
            f"[{audit['start_time']} to {audit['end_time']}]"
        )
        return df, audit
