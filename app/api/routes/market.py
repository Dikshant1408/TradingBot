"""
Market Data & Instrument API endpoints.
"""
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import pandas as pd
from app.data.instruments import instrument_registry, Instrument
from app.data.loader import DataLoader
from app.data.normalizer import CandleNormalizer
from app.core.clock import is_market_open_now, get_ist_now, format_ist
from app.config.settings import get_settings

router = APIRouter(prefix="/api/market", tags=["Market"])
settings = get_settings()


@router.get("/instruments", response_model=List[Instrument])
def get_instruments():
    """List all configured Indian instruments (indices, equities, lots)."""
    return instrument_registry.list_all()


@router.get("/status")
def get_market_status():
    """Check current Indian market session status (09:15-15:30 IST)."""
    is_open, msg = is_market_open_now()
    now_ist = get_ist_now()
    return {
        "is_open": is_open,
        "status_message": msg,
        "current_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "exchange": settings.EXCHANGE_DEFAULT,
        "trading_hours": "09:15 - 15:30 IST"
    }


@router.get("/data/{symbol}")
def preview_market_data(symbol: str, limit: int = 100):
    """Preview normalized historical candle data for a given symbol."""
    df = DataLoader.get_processed(symbol)
    if df is None:
        sample_path = settings.DATA_DIR / "samples" / f"{symbol.upper()}.csv"
        if sample_path.exists():
            df, _ = DataLoader.load_csv(sample_path, symbol)
        else:
            raise HTTPException(status_code=404, detail=f"No dataset found for {symbol}")

    tail_df = df.tail(limit)
    return {
        "symbol": symbol.upper(),
        "total_rows": len(df),
        "columns": list(df.columns),
        "candles": tail_df.to_dict(orient="records")
    }


@router.post("/upload")
async def upload_csv_data(
    file: UploadFile = File(...),
    symbol: str = Form(...)
):
    """Upload custom CSV market data, validate, normalize, and save."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    raw_dir = settings.DATA_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    temp_path = raw_dir / file.filename

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        df, audit = DataLoader.load_csv(temp_path, symbol=symbol.upper())
        processed_path = DataLoader.save_processed(df, symbol=symbol.upper())
        return {
            "message": f"Successfully uploaded and normalized {len(df)} candles for {symbol.upper()}",
            "audit": audit,
            "saved_file": str(processed_path.name)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {str(e)}")


@router.post("/generate-demo")
def generate_demo(symbol: str = "NIFTY50_DEMO", days: int = 180):
    """Generate or refresh synthetic demo dataset (Section 38 compliant)."""
    file_path = DataLoader.generate_demo_dataset(symbol, days=days)
    return {
        "message": f"Generated synthetic demo data for {symbol}",
        "file": str(file_path.name),
        "compliance_note": "DEMO DATA: For local algorithmic testing only."
    }
