"""
System status, logs inspection, and health check API routes.
"""
from pathlib import Path
from fastapi import APIRouter
from app.config.settings import get_settings
from app.core.state import state_manager

router = APIRouter(prefix="/api/system", tags=["System"])
settings = get_settings()


@router.get("/health")
def health_check():
    """System health check and mode indicator."""
    return {
        "status": "HEALTHY",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mode": state_manager.state.mode.value.upper(),
        "bot_status": state_manager.state.status.value,
        "is_emergency_stopped": state_manager.state.is_emergency_stopped,
        "is_kill_switch_active": state_manager.state.is_kill_switch_active
    }


@router.get("/settings")
def get_sanitized_settings():
    """Fetch current settings with secrets redacted."""
    return settings.sanitized_dict()


@router.get("/logs")
def get_recent_logs(lines: int = 100):
    """Retrieve tail of active rotating log file."""
    log_file = settings.LOGS_DIR / "trading_bot.log"
    if not log_file.exists():
        return {"logs": ["No log file generated yet."]}

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:]
            return {"logs": tail_lines}
    except Exception as e:
        return {"logs": [f"Error reading log file: {str(e)}"]}
