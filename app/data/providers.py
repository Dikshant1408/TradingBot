"""
Market Data Provider Abstraction Layer.
Supports CSV, synthetic demo feeds, and external web market data.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import requests
import logging
from app.data.normalizer import CandleNormalizer
from app.data.loader import DataLoader
from app.core.exceptions import DataValidationError

logger = logging.getLogger("trading_bot.data.providers")


class MarketDataProvider(ABC):
    """Abstract interface for all market data sources."""

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data as normalized DataFrame."""
        pass

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Fetch the most recent closing or last traded price."""
        pass


class CsvDataProvider(MarketDataProvider):
    """Provides market data loaded from local processed or sample CSVs."""

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        df = DataLoader.get_processed(symbol, timeframe)
        if df is None:
            # Check samples
            sample_path = DataLoader.generate_demo_dataset(symbol)
            df, _ = DataLoader.load_csv(sample_path, symbol)

        if df.empty:
            raise DataValidationError(f"No historical data found for {symbol}")

        if start_date:
            start_dt = pd.to_datetime(start_date, utc=True)
            df = df[df["timestamp"] >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date, utc=True)
            df = df[df["timestamp"] <= end_dt]

        return df.reset_index(drop=True)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        df = self.get_historical_data(symbol)
        if not df.empty:
            return float(df["close"].iloc[-1])
        return None


class YahooFinanceProvider(MarketDataProvider):
    """
    Retrieves public historical data for Indian tickers (e.g. ^NSEI, RELIANCE.NS).
    Zero API key required; strictly uses public HTTP requests.
    """

    TICKER_MAP = {
        "NIFTY50": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
        "RELIANCE": "RELIANCE.NS",
        "TCS": "TCS.NS",
        "INFY": "INFY.NS",
        "HDFCBANK": "HDFCBANK.NS",
        "ICICIBANK": "ICICIBANK.NS",
        "TATAMOTORS": "TATAMOTORS.NS",
        "SBIN": "SBIN.NS"
    }

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        ticker = self.TICKER_MAP.get(symbol.upper(), f"{symbol.upper()}.NS")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={timeframe}&range=1y"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"Yahoo finance request failed with {resp.status_code} for {ticker}")
                return CsvDataProvider().get_historical_data(symbol, start_date, end_date, timeframe)

            data = resp.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]

            raw_df = pd.DataFrame({
                "timestamp": [datetime.utcfromtimestamp(ts) for ts in timestamps],
                "open": quote["open"],
                "high": quote["high"],
                "low": quote["low"],
                "close": quote["close"],
                "volume": quote.get("volume", [0] * len(timestamps)),
                "symbol": symbol.upper()
            })

            df, _ = CandleNormalizer.normalize_dataframe(raw_df, symbol=symbol.upper())
            DataLoader.save_processed(df, symbol=symbol, timeframe=timeframe)
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch Yahoo Finance data for {symbol}: {e}. Falling back to cached/demo data.")
            return CsvDataProvider().get_historical_data(symbol, start_date, end_date, timeframe)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        try:
            df = self.get_historical_data(symbol)
            if not df.empty:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        return None
