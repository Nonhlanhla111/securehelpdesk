"""Helpers for writing audit-log and security-event rows.

These only add rows to the session. The caller commits, so the log entry is
saved atomically with the action it describes. On paths that then raise an
HTTPException, call `db.commit()` first or the log row is rolled back.
"""
import re

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, SecurityEvent

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def client_ip(request: Request) -> str | None:
    # Behind a reverse proxy this is the proxy's address; configure uvicorn's
    # --proxy-headers / --forwarded-allow-ips when deploying.
    return request.client.host if request.client else None


def _clean(text: str | None, limit: int = 1000) -> str | None:
    if text is None:
        return None
    return _CONTROL_CHARS.sub(" ", text)[:limit]  # stops log-forging via newlines


def audit(db: Session, action: str, *, user_id: int | None = None, entity_type: str | None = None,
          entity_id: int | None = None, ip: str | None = None, details: str | None = None) -> None:
    db.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id,
                    ip_address=ip, details=_clean(details)))


def security_event(db: Session, event_type: str, severity: str, description: str, *,
                   user_id: int | None = None, ip: str | None = None) -> None:
    db.add(SecurityEvent(event_type=event_type, severity=severity, user_id=user_id,
                         ip_address=ip, description=_clean(description)))
