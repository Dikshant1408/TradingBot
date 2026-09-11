"""
Central Audit Trail Logger.
Ensures every critical trading, risk, mode switch, and configuration change
is permanently logged in SQLite for forensic traceability.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.database import SessionLocal, AuditLogModel

logger = logging.getLogger("trading_bot.audit")


def record_audit_log(
    actor: str,
    action: str,
    component: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Safely records an audit log entry in the database.
    Catches any exception so auditing failures never crash execution.
    """
    try:
        details_json = json.dumps(details or {}, default=str)
        db = SessionLocal()
        try:
            entry = AuditLogModel(
                actor=actor,
                action=action,
                component=component,
                details_json=details_json,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(entry)
            db.commit()
            logger.info("AUDIT [%s] %s by %s: %s", component, action, actor, details_json)
        finally:
            db.close()
    except Exception as e:
        logger.error("Failed to record audit log: %s", str(e), exc_info=True)
