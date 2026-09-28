"""Insert the fixed lookup rows (roles, categories, priorities, statuses) if missing,
and optionally bootstrap a first Administrator account on hosts with no terminal access."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import CategoryName, PriorityName, RoleName, StatusName
from app.models import Role, TicketCategory, TicketPriority, TicketStatus, User

log = logging.getLogger("securehelpdesk")


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


def bootstrap_admin(db: Session, email: str | None, name: str | None, password: str | None) -> None:
    """Create the given Administrator account if it doesn't already exist.

    No-op unless all three settings are provided, and never overwrites an
    existing account with the same email (so it's safe to leave the
    environment variables in place indefinitely; this only fires once).
    """
    if not (email and name and password):
        return
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        return
    from app.schemas import RegisterRequest  # reuse the same validation the API applies
    from app.security import hash_password

    try:
        RegisterRequest(email=email, full_name=name, password=password)
    except Exception as exc:
        log.warning("Skipping admin bootstrap: %s", exc)
        return

    role = db.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
    db.add(User(email=email, full_name=name, hashed_password=hash_password(password), role_id=role.id))
    db.commit()
    log.warning("Bootstrapped Administrator account: %s", email)
