import pytest
import pandas as pd
from app.data.normalizer import CandleNormalizer
from app.core.exceptions import DataValidationError


def test_candle_normalization_valid():
    raw_data = {
        "Date": ["2026-01-01 09:15:00", "2026-01-02 09:15:00"],
        "Open": [100.0, 105.0],
        "High": [110.0, 112.0],
        "Low": [98.0, 104.0],
        "Close": [105.0, 110.0],
        "Volume": [5000, 6000]
    }
    df = pd.DataFrame(raw_data)
    clean_df, audit = CandleNormalizer.normalize_dataframe(df, symbol="RELIANCE")

    assert len(clean_df) == 2
    assert "timestamp" in clean_df.columns
    assert clean_df["symbol"].iloc[0] == "RELIANCE"
    assert audit["dropped_invalid_prices"] == 0
    assert audit["dropped_inverted_high_low"] == 0


def test_candle_normalization_rejects_inverted_prices():
    # High < Low is invalid
    raw_data = {
        "timestamp": ["2026-01-01", "2026-01-02"],
        "open": [100.0, 100.0],
        "high": [90.0, 105.0],  # Inverted: high 90 < low 95
        "low": [95.0, 95.0],
        "close": [92.0, 102.0],
        "volume": [100, 100]
    }
    df = pd.DataFrame(raw_data)
    clean_df, audit = CandleNormalizer.normalize_dataframe(df, symbol="TEST")
    assert len(clean_df) == 1  # 1 dropped
    assert audit["dropped_inverted_high_low"] == 1


def test_candle_normalization_deduplicates():
    raw_data = {
        "timestamp": ["2026-01-01 10:00:00", "2026-01-01 10:00:00"],  # Duplicate
        "open": [100.0, 102.0],
        "high": [110.0, 112.0],
        "low": [98.0, 99.0],
        "close": [105.0, 108.0],
        "volume": [1000, 2000]
    }
    df = pd.DataFrame(raw_data)
    clean_df, audit = CandleNormalizer.normalize_dataframe(df, symbol="TEST")
    assert len(clean_df) == 1
    assert audit["dropped_duplicates"] == 1
