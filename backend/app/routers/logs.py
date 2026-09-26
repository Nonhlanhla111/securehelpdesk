"""Audit logs and security events (Administrator only)."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import RoleName, Severity
from app.database import get_db
from app.deps import require_roles
from app.models import AuditLog, SecurityEvent, User
from app.schemas import AuditLogOut, SecurityEventOut

router = APIRouter(prefix="/api", tags=["Audit & Security"])
admin_only = require_roles(RoleName.ADMIN.value)


def _range(col, date_from: date | None, date_to: date | None) -> list:
    conds = []
    if date_from:
        conds.append(col >= datetime.combine(date_from, time.min))
    if date_to:
        conds.append(col < datetime.combine(date_to + timedelta(days=1), time.min))
    return conds


@router.get("/audit-logs", response_model=dict)
def list_audit_logs(
    action: str | None = Query(None, max_length=64),
    user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    conds = _range(AuditLog.timestamp, date_from, date_to)
    if action:
        conds.append(AuditLog.action == action)
    if user_id is not None:
        conds.append(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count(AuditLog.id)).where(*conds))
    rows = db.scalars(select(AuditLog).where(*conds).order_by(AuditLog.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [AuditLogOut.model_validate(r) for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/security-events", response_model=dict)
def list_security_events(
    severity: Severity | None = None,
    event_type: str | None = Query(None, max_length=64),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    conds = _range(SecurityEvent.timestamp, date_from, date_to)
    if severity:
        conds.append(SecurityEvent.severity == severity.value)
    if event_type:
        conds.append(SecurityEvent.event_type == event_type)
    total = db.scalar(select(func.count(SecurityEvent.id)).where(*conds))
    rows = db.scalars(select(SecurityEvent).where(*conds).order_by(SecurityEvent.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [SecurityEventOut.model_validate(r) for r in rows], "total": total,
            "page": page, "page_size": page_size}
