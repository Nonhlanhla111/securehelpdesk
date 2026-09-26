"""Tickets: create, list/search, view, update, assign, comment, history, delete."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.constants import (EMPLOYEE_TRANSITIONS, STAFF_ROLES, STAFF_TRANSITIONS, CategoryName,
                           PriorityName, RoleName, StatusName)
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import (Ticket, TicketCategory, TicketComment, TicketHistory, TicketPriority,
                        TicketStatus, User, utcnow)
from app.schemas import (AssignRequest, CommentCreate, CommentOut, HistoryOut, TicketCreate,
                         TicketOut, TicketPage, TicketUpdate)
from app.services import add_history, get_visible_ticket, lookup_id

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])
staff_only = require_roles(*STAFF_ROLES)
admin_only = require_roles(RoleName.ADMIN.value)


def _is_staff(user: User) -> bool:
    return user.role_name in STAFF_ROLES


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _deny(db: Session, request: Request, user: User, message: str, status: int = 403):
    ip = client_ip(request)
    audit(db, "UNAUTHORIZED_ACCESS", user_id=user.id, ip=ip, details=message)
    security_event(db, "UNAUTHORIZED_ACCESS", "Medium", f"{user.email}: {message}", user_id=user.id, ip=ip)
    db.commit()
    raise HTTPException(status_code=status, detail="You do not have permission to do that")


# ------------------------------------------------------------------ create
@router.post("", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ticket = Ticket(
        title=payload.title, description=payload.description,
        category_id=lookup_id(db, TicketCategory, payload.category.value),
        priority_id=lookup_id(db, TicketPriority, payload.priority.value),
        status_id=lookup_id(db, TicketStatus, StatusName.OPEN.value),
        created_by_id=user.id,
    )
    db.add(ticket)
    db.flush()
    add_history(db, ticket, user, "created", None, StatusName.OPEN.value)
    audit(db, "TICKET_CREATED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id,
          ip=client_ip(request), details=f"{payload.category.value}/{payload.priority.value}")
    db.commit()
    db.refresh(ticket)
    return TicketOut.from_ticket(ticket)


# -------------------------------------------------------------------- list
@router.get("", response_model=TicketPage)
def list_tickets(
    q: str | None = Query(None, max_length=100, description="Ticket ID or text in the title"),
    status: StatusName | None = None,
    category: CategoryName | None = None,
    priority: PriorityName | None = None,
    assigned_to_id: int | None = None,
    unassigned: bool | None = None,
    employee: str | None = Query(None, max_length=100, description="Employee name or email contains"),
    created_from: date | None = None,
    created_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conds = []
    # Visibility rules first - filters can only narrow what the user is already allowed to see.
    if user.role_name == RoleName.EMPLOYEE.value:
        conds.append(Ticket.created_by_id == user.id)
    elif user.role_name == RoleName.AGENT.value:
        conds.append(or_(Ticket.assigned_to_id.is_(None), Ticket.assigned_to_id == user.id,
                         Ticket.created_by_id == user.id))

    if q:
        q = q.strip()
        like = f"%{_escape_like(q)}%"
        text_match = Ticket.title.ilike(like, escape="\\")
        conds.append(or_(text_match, Ticket.id == int(q)) if q.isdigit() and len(q) < 10 else text_match)
    if status:
        conds.append(Ticket.status_id == lookup_id(db, TicketStatus, status.value))
    if category:
        conds.append(Ticket.category_id == lookup_id(db, TicketCategory, category.value))
    if priority:
        conds.append(Ticket.priority_id == lookup_id(db, TicketPriority, priority.value))
    if assigned_to_id is not None:
        conds.append(Ticket.assigned_to_id == assigned_to_id)
    if unassigned:
        conds.append(Ticket.assigned_to_id.is_(None))
    if employee and _is_staff(user):
        like = f"%{_escape_like(employee.strip())}%"
        conds.append(Ticket.created_by.has(or_(User.full_name.ilike(like, escape="\\"),
                                               User.email.ilike(like, escape="\\"))))
    if created_from:
        conds.append(Ticket.created_at >= datetime.combine(created_from, time.min))
    if created_to:
        conds.append(Ticket.created_at < datetime.combine(created_to + timedelta(days=1), time.min))

    total = db.scalar(select(func.count(Ticket.id)).where(*conds))
    rows = db.scalars(select(Ticket).where(*conds).order_by(Ticket.updated_at.desc(), Ticket.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return TicketPage(items=[TicketOut.from_ticket(t) for t in rows], total=total,
                      page=page, page_size=page_size)


# --------------------------------------------------------------------- get
@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, request: Request, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return TicketOut.from_ticket(get_visible_ticket(db, user, ticket_id, request))


# ------------------------------------------------------------------ update
@router.put("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, request: Request,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied")

    staff = _is_staff(user)
    current_status = ticket.status.name

    if staff:
        # Agents may only work tickets assigned to them (accept from the queue first).
        if user.role_name == RoleName.AGENT.value and ticket.assigned_to_id != user.id:
            raise HTTPException(status_code=403, detail="Assign the ticket to yourself before updating it")
    else:
        # Employees: own tickets only (guaranteed by visibility), limited fields.
        forbidden = set(changes) & {"category", "priority"}
        if forbidden:
            _deny(db, request, user, f"employee tried to change {sorted(forbidden)} on ticket #{ticket.id}")
        if ({"title", "description"} & set(changes)) and current_status != StatusName.OPEN.value:
            raise HTTPException(status_code=409, detail="You can only edit a ticket while it is still Open")

    if current_status == StatusName.CLOSED.value:
        raise HTTPException(status_code=409, detail="Closed tickets cannot be modified")

    ip = client_ip(request)

    if "status" in changes:
        new_status = changes["status"].value
        allowed = (STAFF_TRANSITIONS if staff else EMPLOYEE_TRANSITIONS).get(current_status, set())
        if new_status not in allowed:
            hint = " Use POST /assign to move an Open ticket to Assigned." if current_status == "Open" else ""
            raise HTTPException(status_code=400,
                                detail=f"Cannot change status from '{current_status}' to '{new_status}'.{hint}")
        ticket.status_id = lookup_id(db, TicketStatus, new_status)
        ticket.resolved_at = utcnow() if new_status == StatusName.RESOLVED.value else (
            None if new_status == StatusName.IN_PROGRESS.value else ticket.resolved_at)
        add_history(db, ticket, user, "status", current_status, new_status)
        audit(db, "TICKET_STATUS_CHANGED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id,
              ip=ip, details=f"{current_status} -> {new_status}")

    other_fields = []
    if "title" in changes and changes["title"] != ticket.title:
        add_history(db, ticket, user, "title", ticket.title, changes["title"])
        ticket.title = changes["title"]
        other_fields.append("title")
    if "description" in changes and changes["description"] != ticket.description:
        add_history(db, ticket, user, "description", "(edited)", "(edited)")
        ticket.description = changes["description"]
        other_fields.append("description")
    if "category" in changes and changes["category"].value != ticket.category.name:
        add_history(db, ticket, user, "category", ticket.category.name, changes["category"].value)
        ticket.category_id = lookup_id(db, TicketCategory, changes["category"].value)
        other_fields.append("category")
    if "priority" in changes and changes["priority"].value != ticket.priority.name:
        add_history(db, ticket, user, "priority", ticket.priority.name, changes["priority"].value)
        ticket.priority_id = lookup_id(db, TicketPriority, changes["priority"].value)
        other_fields.append("priority")
    if other_fields:
        audit(db, "TICKET_UPDATED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id, ip=ip,
              details="Changed: " + ", ".join(other_fields))

    ticket.updated_at = utcnow()
    db.commit()
    db.expire(ticket)  # reload relationships (status/priority names) after id changes
    return TicketOut.from_ticket(db.get(Ticket, ticket_id))


# ------------------------------------------------------------------ assign
@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(ticket_id: int, request: Request, payload: AssignRequest | None = None,
                  user: User = Depends(staff_only), db: Session = Depends(get_db)):
    """Agents accept a ticket for themselves. Administrators can assign to any active agent/admin."""
    ticket = get_visible_ticket(db, user, ticket_id, request)
    if ticket.status.name in (StatusName.RESOLVED.value, StatusName.CLOSED.value):
        raise HTTPException(status_code=409, detail="Resolved or closed tickets cannot be reassigned")

    target_id = payload.agent_id if payload and payload.agent_id is not None else user.id
    if user.role_name == RoleName.AGENT.value:
        if target_id != user.id:
            _deny(db, request, user, f"agent tried to assign ticket #{ticket.id} to user {target_id}")
        if ticket.assigned_to_id not in (None, user.id):
            raise HTTPException(status_code=409, detail="Ticket is already assigned to someone else")

    target = db.get(User, target_id)
    if not target or not target.is_active or target.role_name not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Assignee must be an active support agent or administrator")

    old_assignee = ticket.assigned_to.full_name if ticket.assigned_to else None
    if ticket.assigned_to_id != target.id:
        add_history(db, ticket, user, "assigned_to", old_assignee, target.full_name)
        ticket.assigned_to_id = target.id
    if ticket.status.name == StatusName.OPEN.value:
        add_history(db, ticket, user, "status", StatusName.OPEN.value, StatusName.ASSIGNED.value)
        ticket.status_id = lookup_id(db, TicketStatus, StatusName.ASSIGNED.value)
    audit(db, "TICKET_ASSIGNED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id,
          ip=client_ip(request), details=f"Assigned to {target.email}")
    ticket.updated_at = utcnow()
    db.commit()
    db.expire(ticket)
    return TicketOut.from_ticket(db.get(Ticket, ticket_id))


# ------------------------------------------------------------------ delete
@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, request: Request, admin: User = Depends(admin_only),
                  db: Session = Depends(get_db)):
    from app.routers.attachments import delete_files_for_ticket
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    files = [a.stored_filename for a in ticket.attachments]
    audit(db, "TICKET_DELETED", user_id=admin.id, entity_type="Ticket", entity_id=ticket.id,
          ip=client_ip(request), details=f"Deleted '{ticket.title}'")
    db.delete(ticket)
    db.commit()
    delete_files_for_ticket(files)


# ---------------------------------------------------------------- comments
@router.post("/{ticket_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(ticket_id: int, payload: CommentCreate, request: Request,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    if ticket.status.name == StatusName.CLOSED.value:
        raise HTTPException(status_code=409, detail="Closed tickets cannot receive new comments")
    if payload.is_internal and not _is_staff(user):
        _deny(db, request, user, f"employee tried to post an internal note on ticket #{ticket.id}")
    comment = TicketComment(ticket_id=ticket.id, author_id=user.id, body=payload.body,
                            is_internal=payload.is_internal)
    db.add(comment)
    ticket.updated_at = utcnow()
    db.flush()
    audit(db, "COMMENT_ADDED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id,
          ip=client_ip(request), details="Internal note" if payload.is_internal else "Public comment")
    db.commit()
    db.refresh(comment)
    return CommentOut.from_comment(comment)


@router.get("/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(ticket_id: int, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    show_internal = _is_staff(user)
    return [CommentOut.from_comment(c) for c in ticket.comments if show_internal or not c.is_internal]


# ----------------------------------------------------------------- history
@router.get("/{ticket_id}/history", response_model=list[HistoryOut])
def ticket_history(ticket_id: int, request: Request, user: User = Depends(staff_only),
                   db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    return [HistoryOut(id=h.id, ticket_id=h.ticket_id, changed_by_id=h.changed_by_id,
                       changed_by_name=h.changed_by.full_name, field=h.field, old_value=h.old_value,
                       new_value=h.new_value, changed_at=h.changed_at) for h in ticket.history]
