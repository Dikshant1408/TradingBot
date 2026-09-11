"""
Execution models for backtesting simulation.
Controls whether orders fill at the next bar's open (realistic) or same bar close.
"""
from enum import Enum


class ExecutionModel(str, Enum):
    NEXT_OPEN = "NEXT_OPEN"    # Default & Recommended: Signal at t close -> fill at t+1 open
    SAME_CLOSE = "SAME_CLOSE"  # Aggressive: Signal at t close -> fill at t close (with spread penalty)
