import json
from pathlib import Path
from fastapi import APIRouter
from app.config.settings import get_settings, process_security_context
from app.core.state import state_manager
from app.database import SessionLocal, AuditLogModel

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
        "is_kill_switch_active": state_manager.state.is_kill_switch_active,
        "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
        "process_authorized": process_security_context.is_authorized(),
        "today_trades_count": state_manager.state.today_trades_count,
        "open_positions_count": state_manager.state.open_positions_count,
        "today_pnl": round(state_manager.state.today_pnl, 2)
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


@router.get("/audit-trail")
def get_audit_trail(limit: int = 100):
    """Retrieve forensic audit trail records from the SQLite store."""
    db = SessionLocal()
    try:
        records = (
            db.query(AuditLogModel)
            .order_by(AuditLogModel.timestamp.desc())
            .limit(limit)
            .all()
        )
        result = []
        for r in records:
            try:
                details = json.loads(r.details_json) if r.details_json else {}
            except Exception:
                details = {"raw": r.details_json}

            result.append({
                "id": r.id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "actor": r.actor,
                "action": r.action,
                "component": r.component,
                "details": details
            })
        return {"audit_logs": result, "total": len(result)}
    finally:
        db.close()
