"""
SQLAlchemy database models for trading bot state, executions, and logs.
All timestamps stored as UTC strings or UTC Datetimes.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.database.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class SettingModel(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class InstrumentModel(Base):
    __tablename__ = "instruments"

    symbol = Column(String(50), primary_key=True)
    exchange = Column(String(20), default="NSE", nullable=False)
    name = Column(String(100), nullable=True)
    instrument_type = Column(String(20), default="EQUITY", nullable=False)  # EQUITY, INDEX, FUTURES, OPTION
    lot_size = Column(Integer, default=1, nullable=False)
    tick_size = Column(Float, default=0.05, nullable=False)
    expiry = Column(String(30), nullable=True)
    strike = Column(Float, nullable=True)
    option_type = Column(String(10), nullable=True)  # CE, PE
    trading_hours = Column(String(50), default="09:15-15:30", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class StrategyConfigModel(Base):
    __tablename__ = "strategies"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), default="1.0.0", nullable=False)
    description = Column(Text, nullable=True)
    parameters_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class BacktestRunModel(Base):
    __tablename__ = "backtests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    strategy_name = Column(String(100), nullable=False)
    strategy_version = Column(String(20), default="1.0.0", nullable=False)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(20), default="1d", nullable=False)
    start_date = Column(String(30), nullable=False)
    end_date = Column(String(30), nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    return_pct = Column(Float, nullable=False)
    cagr = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    slippage_cost = Column(Float, default=0.0)
    params_json = Column(Text, default="{}")
    metrics_json = Column(Text, default="{}")
    equity_curve_json = Column(Text, default="[]")
    trades_json = Column(Text, default="[]")
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ExperimentModel(Base):
    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    hypothesis = Column(Text, nullable=True)
    tags = Column(String(200), nullable=True)
    run_id = Column(String(36), ForeignKey("backtests.id"), nullable=False)
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(50), nullable=False)
    quality_score = Column(Float, default=0.0)
    return_pct = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    client_order_id = Column(String(100), unique=True, nullable=False)
    mode = Column(String(20), nullable=False)  # BACKTEST, PAPER, LIVE
    symbol = Column(String(50), nullable=False)
    exchange = Column(String(20), default="NSE", nullable=False)
    side = Column(String(10), nullable=False)  # BUY, SELL
    order_type = Column(String(20), default="MARKET", nullable=False)  # MARKET, LIMIT
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, FILLED, REJECTED, CANCELLED
    filled_quantity = Column(Integer, default=0)
    avg_fill_price = Column(Float, default=0.0)
    rejection_reason = Column(Text, nullable=True)
    strategy_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    fills = relationship("FillModel", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_orders_mode_symbol", "mode", "symbol"),
        Index("idx_orders_status", "status"),
    )


class FillModel(Base):
    __tablename__ = "fills"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    brokerage = Column(Float, default=0.0)
    stt = Column(Float, default=0.0)
    exchange_charges = Column(Float, default=0.0)
    gst = Column(Float, default=0.0)
    sebi_charges = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    total_costs = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), default=utc_now)

    order = relationship("OrderModel", back_populates="fills")


class PositionModel(Base):
    __tablename__ = "positions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    mode = Column(String(20), nullable=False)  # PAPER, LIVE
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # LONG, SHORT
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_positions_mode_symbol", "mode", "symbol", unique=True),
    )


class TradeModel(Base):
    __tablename__ = "trades"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    mode = Column(String(20), nullable=False)  # BACKTEST, PAPER, LIVE
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Integer, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    gross_pnl = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)
    slippage_cost = Column(Float, default=0.0)
    return_pct = Column(Float, default=0.0)
    strategy_name = Column(String(100), default="MA_Crossover")
    strategy_reason = Column(Text, nullable=True)
    indicator_snapshot_json = Column(Text, default="{}")  # Stored indicators for 'Why did the bot trade?'
    created_at = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("idx_trades_mode_symbol", "mode", "symbol"),
        Index("idx_trades_entry_time", "entry_time"),
    )


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    mode = Column(String(20), nullable=False)  # PAPER, LIVE
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    cash = Column(Float, nullable=False)
    invested_value = Column(Float, default=0.0)
    total_equity = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    today_pnl = Column(Float, default=0.0)
    drawdown_pct = Column(Float, default=0.0)


class RiskEventModel(Base):
    __tablename__ = "risk_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    mode = Column(String(20), nullable=False)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="WARNING")  # INFO, WARNING, CRITICAL, HALT
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}")


class SystemEventModel(Base):
    __tablename__ = "system_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    level = Column(String(20), default="INFO")
    component = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime(timezone=True), default=utc_now)
    actor = Column(String(50), default="SYSTEM", nullable=False)  # SYSTEM, USER, RISK_ENGINE
    action = Column(String(100), nullable=False)  # CONFIG_CHANGE, KILL_SWITCH_TOGGLE, EMERGENCY_STOP, ORDER_REJECT, etc.
    component = Column(String(50), nullable=False)
    details_json = Column(Text, default="{}")

    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_action", "action"),
    )
