"""
Data loader and demo dataset manager for Indian market instruments.
"""
import logging
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from app.config.settings import get_settings
from app.data.normalizer import CandleNormalizer
from app.core.exceptions import DataValidationError

logger = logging.getLogger("trading_bot.data.loader")
settings = get_settings()


class DataLoader:
    """
    Manages loading, caching, and sample data generation.
    """

    @classmethod
    def load_csv(cls, file_path: Path | str, symbol: str) -> Tuple[pd.DataFrame, dict]:
        """
        Load a CSV file from disk, validate and normalize it.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        try:
            raw_df = pd.read_csv(file_path)
        except Exception as e:
            raise DataValidationError(f"Could not read CSV file {file_path.name}: {e}")

        df, audit = CandleNormalizer.normalize_dataframe(raw_df, symbol=symbol)
        return df, audit

    @classmethod
    def save_processed(cls, df: pd.DataFrame, symbol: str, timeframe: str = "1d") -> Path:
        """
        Save normalized dataframe to processed storage directory.
        """
        dest_dir = settings.DATA_DIR / "processed"
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_path = dest_dir / f"{symbol.upper()}_{timeframe.lower()}.csv"
        df.to_csv(file_path, index=False)
        logger.info(f"Saved processed data to {file_path}")
        return file_path

    @classmethod
    def get_processed(cls, symbol: str, timeframe: str = "1d") -> Optional[pd.DataFrame]:
        """
        Retrieve cached processed data if available.
        """
        file_path = settings.DATA_DIR / "processed" / f"{symbol.upper()}_{timeframe.lower()}.csv"
        if file_path.exists():
            df = pd.read_csv(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df
        return None

    @classmethod
    def generate_demo_dataset(
        cls,
        symbol: str = "NIFTY50_DEMO",
        days: int = 180,
        start_price: float = 22000.0,
        daily_volatility: float = 0.012
    ) -> Path:
        """
        Generate clearly labeled synthetic demo dataset for system testing.
        COMPLIANCE NOTE (Section 38): Clearly labeled as DEMO DATA.
        """
        samples_dir = settings.DATA_DIR / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)
        file_path = samples_dir / f"{symbol}.csv"

        np.random.seed(42)  # Deterministic seed for reproducible testing
        base_date = datetime.now(pytz.timezone("Asia/Kolkata")) - timedelta(days=days + 10)

        records = []
        current_close = start_price

        for i in range(days + 10):
            current_date = base_date + timedelta(days=i)
            # Skip weekends
            if current_date.weekday() >= 5:
                continue

            # Candle timestamp set to standard market close 15:30 IST
            candle_time = current_date.replace(hour=15, minute=30, second=0, microsecond=0)
            utc_candle_time = candle_time.astimezone(pytz.UTC)

            # Realistic geometric random walk
            drift = 0.0004  # Slight upward drift
            shock = np.random.normal(0, daily_volatility)
            pct_change = drift + shock

            day_open = current_close * (1 + np.random.normal(0, daily_volatility * 0.3))
            day_close = day_open * (1 + pct_change)
            
            intra_high = max(day_open, day_close) * (1 + abs(np.random.normal(0, daily_volatility * 0.5)))
            intra_low = min(day_open, day_close) * (1 - abs(np.random.normal(0, daily_volatility * 0.5)))
            volume = int(np.random.lognormal(mean=14, sigma=0.5))

            records.append({
                "timestamp": utc_candle_time.isoformat(),
                "open": round(day_open, 2),
                "high": round(intra_high, 2),
                "low": round(intra_low, 2),
                "close": round(day_close, 2),
                "volume": volume,
                "symbol": symbol
            })
            current_close = day_close

        df = pd.DataFrame(records)
        df.to_csv(file_path, index=False)
        logger.info(f"Generated synthetic demo dataset {file_path} with {len(df)} candles.")

        # Also store directly in processed
        cls.save_processed(df, symbol=symbol, timeframe="1d")
        return file_path


def initialize_demo_data():
    """Ensure standard demo datasets exist on startup."""
    nifty_sample = settings.DATA_DIR / "samples" / "NIFTY50_DEMO.csv"
    if not nifty_sample.exists():
        DataLoader.generate_demo_dataset("NIFTY50_DEMO", days=250, start_price=22500.0)

    reliance_sample = settings.DATA_DIR / "samples" / "RELIANCE_DEMO.csv"
    if not reliance_sample.exists():
        DataLoader.generate_demo_dataset("RELIANCE_DEMO", days=250, start_price=2850.0)
