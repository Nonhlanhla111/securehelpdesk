"""Insert the fixed lookup rows (roles, categories, priorities, statuses) if missing."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CategoryName, PriorityName, RoleName, StatusName
from app.models import Role, TicketCategory, TicketPriority, TicketStatus


def seed_lookups(db: Session) -> None:
    def ensure(model, names, **extra):
        existing = set(db.scalars(select(model.name)))
        for i, name in enumerate(names, start=1):
            if name not in existing:
                row = model(name=name, **({"rank": i} if extra.get("ranked") else {}))
                db.add(row)

    ensure(Role, [r.value for r in RoleName])
    ensure(TicketCategory, [c.value for c in CategoryName])
    ensure(TicketPriority, [p.value for p in PriorityName], ranked=True)
    ensure(TicketStatus, [s.value for s in StatusName])
    db.commit()
