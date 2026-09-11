"""
Historical Market Data Quality Validation Engine.
Pre-flight audit for historical OHLCV data prior to backtest execution.
Detects missing candles, irregular timestamp intervals, price anomalies, and suspicious spikes.
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from pydantic import BaseModel


class DataQualityReport(BaseModel):
    is_valid: bool
    quality_score: float  # 0 to 100
    total_candles: int
    date_range_start: str
    date_range_end: str
    missing_candle_count: int
    zero_negative_price_count: int
    high_low_violation_count: int
    zero_volume_count: int
    abnormal_spike_count: int
    anomalies: List[Dict[str, Any]]
    summary: str


class DataQualityValidator:
    """
    Validates data integrity before allowing backtest execution.
    Prevents garbage-in, garbage-out backtest delusions.
    """

    @classmethod
    def validate(cls, df: pd.DataFrame, symbol: str) -> DataQualityReport:
        if df.empty:
            return DataQualityReport(
                is_valid=False,
                quality_score=0.0,
                total_candles=0,
                date_range_start="",
                date_range_end="",
                missing_candle_count=0,
                zero_negative_price_count=0,
                high_low_violation_count=0,
                zero_volume_count=0,
                abnormal_spike_count=0,
                anomalies=[{"severity": "CRITICAL", "message": "DataFrame is empty"}],
                summary="Failing: Empty dataset."
            )

        anomalies: List[Dict[str, Any]] = []
        deductions = 0.0

        # Required columns check
        req_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_cols = [c for c in req_cols if c not in df.columns]
        if missing_cols:
            return DataQualityReport(
                is_valid=False,
                quality_score=0.0,
                total_candles=len(df),
                date_range_start="",
                date_range_end="",
                missing_candle_count=0,
                zero_negative_price_count=0,
                high_low_violation_count=0,
                zero_volume_count=0,
                abnormal_spike_count=0,
                anomalies=[{"severity": "CRITICAL", "message": f"Missing required OHLCV columns: {missing_cols}"}],
                summary="Failing: Corrupted schema."
            )

        # Ensure sorted by timestamp
        df_sorted = df.copy()
        df_sorted["timestamp"] = pd.to_datetime(df_sorted["timestamp"])
        df_sorted = df_sorted.sort_values("timestamp").reset_index(drop=True)

        start_str = df_sorted["timestamp"].iloc[0].strftime("%Y-%m-%d %H:%M")
        end_str = df_sorted["timestamp"].iloc[-1].strftime("%Y-%m-%d %H:%M")

        # 1. Zero or negative prices
        zero_neg = (
            (df_sorted["open"] <= 0) |
            (df_sorted["high"] <= 0) |
            (df_sorted["low"] <= 0) |
            (df_sorted["close"] <= 0)
        ).sum()
        if zero_neg > 0:
            deductions += min(40.0, zero_neg * 10.0)
            anomalies.append({
                "severity": "CRITICAL",
                "message": f"Found {zero_neg} candles with zero or negative prices."
            })

        # 2. High-Low Violations (High < Low or Open/Close outside High/Low)
        hl_viol = (
            (df_sorted["high"] < df_sorted["low"]) |
            (df_sorted["open"] > df_sorted["high"]) |
            (df_sorted["open"] < df_sorted["low"]) |
            (df_sorted["close"] > df_sorted["high"]) |
            (df_sorted["close"] < df_sorted["low"])
        ).sum()
        if hl_viol > 0:
            deductions += min(40.0, hl_viol * 10.0)
            anomalies.append({
                "severity": "CRITICAL",
                "message": f"Found {hl_viol} candles violating High/Low range invariants."
            })

        # 3. Abnormal price jumps (> 15% single bar move)
        pct_moves = df_sorted["close"].pct_change().abs()
        spikes = (pct_moves > 0.15).sum()
        if spikes > 0:
            deductions += min(20.0, spikes * 5.0)
            anomalies.append({
                "severity": "WARNING",
                "message": f"Found {spikes} single-bar price moves exceeding 15%. Verify stock split/bonus or bad ticks."
            })

        # 4. Zero Volume bars
        zero_vol = (df_sorted["volume"] <= 0).sum()
        if zero_vol > 0 and len(df_sorted) > 10:
            pct_zero_vol = (zero_vol / len(df_sorted)) * 100.0
            if pct_zero_vol > 20.0:
                deductions += 15.0
                anomalies.append({
                    "severity": "WARNING",
                    "message": f"{zero_vol} candles ({pct_zero_vol:.1f}%) have zero traded volume."
                })

        # 5. Timestamp duplicate check
        dup_ts = df_sorted["timestamp"].duplicated().sum()
        if dup_ts > 0:
            deductions += min(30.0, dup_ts * 5.0)
            anomalies.append({
                "severity": "CRITICAL",
                "message": f"Found {dup_ts} duplicate timestamps in series."
            })

        quality_score = max(0.0, min(100.0, round(100.0 - deductions, 1)))
        is_valid = (quality_score >= 50.0) and (zero_neg == 0) and (hl_viol == 0)

        summary_status = "PASS (Clean data)" if is_valid else "FAIL (Data anomalies detected)"
        return DataQualityReport(
            is_valid=is_valid,
            quality_score=quality_score,
            total_candles=len(df_sorted),
            date_range_start=start_str,
            date_range_end=end_str,
            missing_candle_count=int(dup_ts),
            zero_negative_price_count=int(zero_neg),
            high_low_violation_count=int(hl_viol),
            zero_volume_count=int(zero_vol),
            abnormal_spike_count=int(spikes),
            anomalies=anomalies,
            summary=f"{summary_status} - Quality Score: {quality_score}/100 across {len(df_sorted)} candles."
        )
