"""
Application Settings and Configuration Management.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional
from datetime import datetime, timezone, timedelta
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Central application settings loaded from environment or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Application Settings
    APP_NAME: str = "QuantDesk India"
    APP_VERSION: str = "1.0.0"
    APP_MODE: Literal["backtest", "paper", "live"] = "paper"
    DEBUG: bool = False
    SECRET_KEY: str = "local-dev-secret-key-insecure-only-for-localhost"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Paths
    BASE_PATH: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'trading_bot.db'}"

    # Timezone & Calendar (Internally UTC, display in IST)
    TIMEZONE: str = "Asia/Kolkata"
    EXCHANGE_DEFAULT: str = "NSE"

    # Capital & Virtual Account
    INITIAL_CAPITAL: float = 100000.0  # ₹1 Lakh default

    # Risk Management Guardrails
    MAX_DAILY_LOSS: float = 5000.0  # ₹5,000 max daily loss
    MAX_DRAWDOWN_PERCENT: float = 0.05  # 5% max drawdown
    MAX_TRADES_PER_DAY: int = 5
    MAX_POSITION_SIZE_VALUE: float = 50000.0  # Max ₹50,000 per single position
    MAX_OPEN_POSITIONS: int = 3
    KILL_SWITCH: bool = False  # Persistent kill switch (if True, live trading is strictly blocked)

    # Indian Market Cost Parameters (NSE Equity Intraday Defaults)
    DEFAULT_BROKERAGE_PER_ORDER: float = 20.0  # Flat ₹20 per executed order or 0.03%
    DEFAULT_STT_RATE: float = 0.00025  # 0.025% on sell for equity intraday
    DEFAULT_EXCHANGE_TURNOVER_RATE: float = 0.0000297  # NSE ~0.00297%
    DEFAULT_GST_RATE: float = 0.18  # 18% GST on brokerage + txn charges
    DEFAULT_SEBI_RATE: float = 0.000001  # ₹10 per crore (0.0001%)
    DEFAULT_STAMP_DUTY_RATE: float = 0.00003  # 0.003% on buy
    DEFAULT_SLIPPAGE_PCT: float = 0.0005  # 0.05% slippage

    # Hard Live Trading Kill Flags
    # Independent hard flag: even if APP_MODE='live', this must be explicitly True
    LIVE_TRADING_ENABLED: bool = False

    # Optional Telegram Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_ENABLED: bool = False

    # Broker Credentials (Disabled by default)
    BROKER_NAME: Optional[str] = None
    BROKER_API_KEY: Optional[str] = None
    BROKER_API_SECRET: Optional[str] = None
    BROKER_USER_ID: Optional[str] = None
    BROKER_PASSWORD: Optional[str] = None
    BROKER_TOTP_KEY: Optional[str] = None


    def sanitized_dict(self) -> dict:
        """
        Return settings dictionary with sensitive fields redacted.
        Safe for API endpoints and logs.
        """
        data = self.model_dump()
        sensitive_keys = [
            "SECRET_KEY",
            "TELEGRAM_BOT_TOKEN",
            "BROKER_API_KEY",
            "BROKER_API_SECRET",
            "BROKER_PASSWORD",
            "BROKER_TOTP_KEY",
        ]
        for key in sensitive_keys:
            val = data.get(key)
            if val:
                data[key] = "********" if len(str(val)) <= 4 else f"{str(val)[:2]}****{str(val)[-2:]}"
            else:
                data[key] = None
        return data


class LiveTradingSession:
    def __init__(self, token: str, authorized_at: datetime, expires_at: datetime, authorized_by: str):
        self.token = token
        self.authorized_at = authorized_at
        self.expires_at = expires_at
        self.authorized_by = authorized_by

    @property
    def is_expired(self) -> bool:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def remaining_seconds(self) -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if now >= self.expires_at:
            return 0
        return int((self.expires_at - now).total_seconds())


class ProcessSecurityContext:
    """
    Ephemeral in-memory authorization store for live trading.
    STRICT SAFETY RULE: Never saved to disk or DB.
    Whenever the process reboots, live authorization is instantly wiped out.
    Enforces a strict sliding 15-minute time-to-live (TTL) session token.
    """
    def __init__(self, session_ttl_minutes: int = 15):
        self._session: Optional[LiveTradingSession] = None
        self.session_ttl_minutes = session_ttl_minutes

    def authorize_session(self, user_confirmation: str, ttl_minutes: Optional[int] = None) -> Optional[LiveTradingSession]:
        from datetime import datetime, timezone, timedelta
        import uuid
        if user_confirmation == "I CONFIRM LIVE TRADING AT MY OWN RISK":
            now = datetime.now(timezone.utc)
            ttl = ttl_minutes or self.session_ttl_minutes
            expires = now + timedelta(minutes=ttl)
            token = f"live_sess_{uuid.uuid4().hex[:16]}"
            self._session = LiveTradingSession(
                token=token,
                authorized_at=now,
                expires_at=expires,
                authorized_by="LOCAL_USER_MANUAL_OVERRIDE"
            )
            return self._session
        return None

    def revoke_session(self) -> None:
        self._session = None

    def is_authorized(self, token: Optional[str] = None) -> bool:
        if self._session is None:
            return False
        if self._session.is_expired:
            self._session = None
            return False
        if token is not None and self._session.token != token:
            return False
        return True

    def get_session_info(self) -> Optional[dict]:
        if self._session is None:
            return None
        if self._session.is_expired:
            self._session = None
            return None
        return {
            "token": self._session.token,
            "authorized_at": self._session.authorized_at.isoformat(),
            "expires_at": self._session.expires_at.isoformat(),
            "remaining_seconds": self._session.remaining_seconds,
            "authorized_by": self._session.authorized_by
        }


process_security_context = ProcessSecurityContext()


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton.
    """
    # Ensure required base directories exist
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data" / "samples").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
    return Settings()
