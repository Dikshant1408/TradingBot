"""
Market Data Provider Abstraction Layer.
Strictly separates Real Market Feeds, Local Uploaded CSVs, and Synthetic Demo Data.
Guarantees NO SILENT FALLBACK to demo data when real data requests fail.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import logging
from app.data.normalizer import CandleNormalizer
from app.data.loader import DataLoader
from app.core.exceptions import DataValidationError

logger = logging.getLogger("trading_bot.data.providers")


class MarketDataSource(str, Enum):
    REAL_YAHOO_FEED = "REAL_YAHOO_FEED"
    LOCAL_CSV_IMPORT = "LOCAL_CSV_IMPORT"
    DEMO_SYNTHETIC = "DEMO_SYNTHETIC"


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


class DemoDataProvider(MarketDataProvider):
    """
    Explicit provider for synthetic demo datasets.
    ONLY invoked when a user explicitly chooses a DEMO symbol (e.g. NIFTY50_DEMO).
    """

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        clean_symbol = symbol.upper()
        sample_path = DataLoader.generate_demo_dataset(clean_symbol)
        df, _ = DataLoader.load_csv(sample_path, clean_symbol)

        if df.empty:
            raise DataValidationError(f"Could not generate demo dataset for {clean_symbol}")

        if start_date:
            start_dt = pd.to_datetime(start_date, utc=True)
            df = df[df["timestamp"] >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date, utc=True)
            df = df[df["timestamp"] <= end_dt]

        df = df.reset_index(drop=True)
        df["data_source"] = MarketDataSource.DEMO_SYNTHETIC.value
        df["is_demo"] = True
        return df

    def get_latest_price(self, symbol: str) -> Optional[float]:
        df = self.get_historical_data(symbol)
        if not df.empty:
            return float(df["close"].iloc[-1])
        return None


class CsvDataProvider(MarketDataProvider):
    """
    Provides market data loaded strictly from locally uploaded or processed CSVs.
    Will NEVER silently invent synthetic demo data if a file is missing.
    """

    def get_historical_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        clean_sym = symbol.upper()
        df = DataLoader.get_processed(clean_sym, timeframe)
        if df is None:
            raise DataValidationError(
                f"No processed CSV data found for '{clean_sym}'. "
                "Please upload a CSV file or fetch real market data. "
                "System will NOT silently generate demo data for real instruments."
            )

        if df.empty:
            raise DataValidationError(f"Dataset for {clean_sym} is empty.")

        if start_date:
            start_dt = pd.to_datetime(start_date, utc=True)
            df = df[df["timestamp"] >= start_dt]

        if end_date:
            end_dt = pd.to_datetime(end_date, utc=True)
            df = df[df["timestamp"] <= end_dt]

        df = df.reset_index(drop=True)
        df["data_source"] = MarketDataSource.LOCAL_CSV_IMPORT.value
        df["is_demo"] = False
        return df

    def get_latest_price(self, symbol: str) -> Optional[float]:
        try:
            df = self.get_historical_data(symbol)
            if not df.empty:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        return None


class YahooFinanceProvider(MarketDataProvider):
    """
    Retrieves public historical data for Indian tickers (e.g. ^NSEI, RELIANCE.NS).
    Zero API key required; strictly uses public HTTP requests.
    FAILS FAST: Never falls back silently to demo/synthetic data!
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
        clean_sym = symbol.upper()
        ticker = self.TICKER_MAP.get(clean_sym, f"{clean_sym}.NS")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={timeframe}&range=1y"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            resp = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as req_err:
            msg = (
                f"Failed to connect to Yahoo Finance for '{clean_sym}' ({ticker}): {req_err}. "
                "Network request failed. System will NOT fall back to synthetic demo data. "
                "To test offline, explicitly select a '_DEMO' instrument."
            )
            logger.error(msg)
            raise DataValidationError(msg)

        if resp.status_code != 200:
            msg = (
                f"Yahoo Finance returned HTTP {resp.status_code} for ticker '{ticker}'. "
                "Market data fetch failed. System will NOT silently use synthetic/demo data. "
                "Please verify symbol or try again later."
            )
            logger.error(msg)
            raise DataValidationError(msg)

        try:
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
                "symbol": clean_sym
            })

            df, _ = CandleNormalizer.normalize_dataframe(raw_df, symbol=clean_sym)
            DataLoader.save_processed(df, symbol=clean_sym, timeframe=timeframe)
            df["data_source"] = MarketDataSource.REAL_YAHOO_FEED.value
            df["is_demo"] = False
            return df
        except Exception as e:
            msg = (
                f"Failed to parse Yahoo Finance market data payload for {clean_sym}: {e}. "
                "Download aborted to prevent corrupted or synthetic fallback."
            )
            logger.error(msg)
            raise DataValidationError(msg)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        try:
            df = self.get_historical_data(symbol)
            if not df.empty:
                return float(df["close"].iloc[-1])
        except Exception:
            pass
        return None


class MarketDataService:
    """
    Authoritative Market Data Dispatcher.
    Ensures that Demo requests only yield Demo data, and Real requests only yield Real data.
    """

    @classmethod
    def is_demo_symbol(cls, symbol: str) -> bool:
        s = symbol.upper()
        return s.endswith("_DEMO") or s.startswith("DEMO_") or s == "DEMO"

    @classmethod
    def get_historical_candles(
        cls,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = "1d"
    ) -> pd.DataFrame:
        clean_sym = symbol.upper()

        # 1. If symbol is explicitly a demo instrument, use DemoDataProvider
        if cls.is_demo_symbol(clean_sym):
            return DemoDataProvider().get_historical_data(clean_sym, start_date, end_date, timeframe)

        # 2. Check if user has a verified local processed CSV
        processed_df = DataLoader.get_processed(clean_sym, timeframe)
        if processed_df is not None and not processed_df.empty:
            processed_df["data_source"] = MarketDataSource.LOCAL_CSV_IMPORT.value
            processed_df["is_demo"] = False
            return processed_df

        # 3. Otherwise fetch real feed from YahooFinanceProvider (fails fast if down)
        return YahooFinanceProvider().get_historical_data(clean_sym, start_date, end_date, timeframe)
