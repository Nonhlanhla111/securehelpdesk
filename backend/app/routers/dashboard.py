"""Role-specific dashboards and (staff) reports."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import STAFF_ROLES, PriorityName, RoleName, StatusName
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (AuditLog, SecurityEvent, Ticket, TicketCategory, TicketPriority,
                        TicketStatus, User, utcnow)
from app.schemas import AuditLogOut, SecurityEventOut, TicketOut
from app.services import lookup_id

router = APIRouter(prefix="/api", tags=["Dashboard & Reports"])


def _count(db: Session, *conds) -> int:
    return db.scalar(select(func.count(Ticket.id)).where(*conds)) or 0


def _recent(db: Session, *conds, limit: int = 5):
    rows = db.scalars(select(Ticket).where(*conds).order_by(Ticket.updated_at.desc()).limit(limit)).all()
    return [TicketOut.from_ticket(t) for t in rows]


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = lambda name: lookup_id(db, TicketStatus, name)  # noqa: E731
    pr = lambda name: lookup_id(db, TicketPriority, name)  # noqa: E731
    role = user.role_name

    if role == RoleName.EMPLOYEE.value:
        mine = Ticket.created_by_id == user.id
        return {
            "role": role,
            "open_tickets": _count(db, mine, Ticket.status_id.in_([st("Open"), st("Assigned")])),
            "in_progress": _count(db, mine, Ticket.status_id == st("In Progress")),
            "resolved": _count(db, mine, Ticket.status_id == st("Resolved")),
            "recently_updated": _recent(db, mine),
        }

    if role == RoleName.AGENT.value:
        visible = or_(Ticket.assigned_to_id.is_(None), Ticket.assigned_to_id == user.id)
        active = Ticket.status_id.notin_([st("Resolved"), st("Closed")])
        return {
            "role": role,
            "open_tickets": _count(db, Ticket.status_id == st("Open")),
            "assigned_to_me": _count(db, Ticket.assigned_to_id == user.id, active),
            "high_priority": _count(db, visible, active, Ticket.priority_id == pr("High")),
            "critical": _count(db, visible, active, Ticket.priority_id == pr("Critical")),
            "awaiting_resolution": _count(db, Ticket.assigned_to_id == user.id,
                                          Ticket.status_id == st("In Progress")),
            "recently_updated": _recent(db, visible),
        }

    since = utcnow() - timedelta(hours=24)
    active = Ticket.status_id.notin_([st("Resolved"), st("Closed")])
    return {
        "role": role,
        "total_users": db.scalar(select(func.count(User.id))),
        "active_users": db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))),
        "total_tickets": _count(db),
        "open_tickets": _count(db, Ticket.status_id == st("Open")),
        "critical_tickets": _count(db, active, Ticket.priority_id == pr("Critical")),
        "security_events_24h": db.scalar(select(func.count(SecurityEvent.id))
                                         .where(SecurityEvent.timestamp >= since)),
        "recent_activity": [AuditLogOut.model_validate(a) for a in
                            db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(10))],
        "recent_security_events": [SecurityEventOut.model_validate(e) for e in
                                   db.scalars(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(10))],
    }


@router.get("/reports/summary")
def report_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(require_roles(*STAFF_ROLES)),
    db: Session = Depends(get_db),
):
    """Ticket statistics for a period (default: last 30 days). Security events: admins only."""
    date_to = date_to or utcnow().date()
    date_from = date_from or (date_to - timedelta(days=30))
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to + timedelta(days=1), time.min)
    in_period = [Ticket.created_at >= start, Ticket.created_at < end]

    def grouped(model, fk_col):
        rows = db.execute(select(model.name, func.count(Ticket.id)).join(Ticket, fk_col == model.id)
                          .where(*in_period).group_by(model.name)).all()
        return {name: n for name, n in rows}

    closed_id, resolved_id = lookup_id(db, TicketStatus, "Closed"), lookup_id(db, TicketStatus, "Resolved")
    per_agent = db.execute(
        select(User.full_name, func.count(Ticket.id)).join(Ticket, Ticket.assigned_to_id == User.id)
        .where(*in_period).group_by(User.full_name)).all()

    report = {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "tickets_created": _count(db, *in_period),
        "tickets_resolved": _count(db, *in_period, Ticket.status_id.in_([resolved_id, closed_id])),
        "open_vs_closed": {
            "closed": _count(db, *in_period, Ticket.status_id == closed_id),
            "not_closed": _count(db, *in_period, Ticket.status_id != closed_id),
        },
        "by_category": grouped(TicketCategory, Ticket.category_id),
        "by_priority": grouped(TicketPriority, Ticket.priority_id),
        "by_status": grouped(TicketStatus, Ticket.status_id),
        "assigned_per_agent": {name: n for name, n in per_agent},
    }
    if user.role_name == RoleName.ADMIN.value:
        ev = db.execute(select(SecurityEvent.event_type, func.count(SecurityEvent.id))
                        .where(SecurityEvent.timestamp >= start, SecurityEvent.timestamp < end)
                        .group_by(SecurityEvent.event_type)).all()
        report["security_events_by_type"] = {t: n for t, n in ev}
    return report
