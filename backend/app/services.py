"""Shared ticket helpers: lookups, object-level access checks, history."""
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.constants import RoleName
from app.models import Ticket, TicketHistory, User


def lookup_id(db: Session, model, name: str) -> int:
    return db.scalar(select(model.id).where(model.name == name))


def can_view_ticket(user: User, ticket: Ticket) -> bool:
    """Object-level authorization (prevents IDOR: guessing another ticket's ID).

    Employee -> only tickets they created.
    Agent    -> unassigned tickets (the shared queue), tickets assigned to them, or their own.
    Admin    -> everything.
    """
    role = user.role_name
    if role == RoleName.ADMIN.value:
        return True
    if ticket.created_by_id == user.id:
        return True
    if role == RoleName.AGENT.value:
        return ticket.assigned_to_id is None or ticket.assigned_to_id == user.id
    return False


def get_visible_ticket(db: Session, user: User, ticket_id: int, request: Request) -> Ticket:
    """Return the ticket or 404. A ticket you may not see looks exactly like one that doesn't exist,
    but the attempt is written to the audit log and security events."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not can_view_ticket(user, ticket):
        ip = client_ip(request)
        desc = f"{user.email} ({user.role_name}) attempted to access ticket #{ticket_id}"
        audit(db, "UNAUTHORIZED_ACCESS", user_id=user.id, entity_type="Ticket", entity_id=ticket_id,
              ip=ip, details=desc)
        security_event(db, "UNAUTHORIZED_ACCESS", "Medium", desc, user_id=user.id, ip=ip)
        db.commit()
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def add_history(db: Session, ticket: Ticket, user: User, field: str, old, new) -> None:
    db.add(TicketHistory(ticket_id=ticket.id, changed_by_id=user.id, field=field,
                         old_value=None if old is None else str(old)[:500],
                         new_value=None if new is None else str(new)[:500]))
