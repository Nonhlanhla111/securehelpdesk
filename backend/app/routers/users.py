"""User administration (Administrator only), plus a small agent list for assignment."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.constants import STAFF_ROLES, RoleName
from app.database import get_db
from app.deps import require_roles
from app.models import Role, User
from app.schemas import AdminCreateUser, UserBrief, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["Users"])
admin_only = require_roles(RoleName.ADMIN.value)
staff_only = require_roles(*STAFF_ROLES)


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=dict)
def list_users(
    q: str | None = Query(None, max_length=100),
    role: RoleName | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _admin: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    conds = []
    if q:
        like = f"%{_escape_like(q.strip())}%"
        conds.append(or_(User.email.ilike(like, escape="\\"), User.full_name.ilike(like, escape="\\")))
    if role:
        conds.append(User.role.has(Role.name == role.value))
    if is_active is not None:
        conds.append(User.is_active == is_active)
    total = db.scalar(select(func.count(User.id)).where(*conds))
    rows = db.scalars(select(User).where(*conds).order_by(User.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [UserOut.from_user(u) for u in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/agents", response_model=list[UserBrief])
def list_agents(_staff: User = Depends(staff_only), db: Session = Depends(get_db)):
    """Active support agents/admins - used to pick an assignee."""
    rows = db.scalars(select(User).where(User.is_active.is_(True), User.role.has(Role.name.in_(STAFF_ROLES)))
                      .order_by(User.full_name)).all()
    return [UserBrief(id=u.id, full_name=u.full_name) for u in rows]


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: AdminCreateUser, request: Request, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    role = db.scalar(select(Role).where(Role.name == payload.role.value))
    user = User(email=email, full_name=payload.full_name, hashed_password=hash_password(payload.password),
                role_id=role.id)
    db.add(user)
    db.flush()
    ip = client_ip(request)
    audit(db, "ACCOUNT_CREATED", user_id=admin.id, entity_type="User", entity_id=user.id, ip=ip,
          details=f"Admin created {email} as {payload.role.value}")
    if payload.role != RoleName.EMPLOYEE:
        security_event(db, "PRIVILEGED_ACCOUNT_CREATED", "Medium",
                       f"{admin.email} created {payload.role.value} account {email}", user_id=admin.id, ip=ip)
    db.commit()
    db.refresh(user)
    return UserOut.from_user(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, _admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.from_user(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, request: Request, admin: User = Depends(admin_only),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    ip = client_ip(request)
    data = payload.model_fields_set

    # An admin can't lock themselves out or strip their own admin rights by accident.
    if user.id == admin.id and (payload.is_active is False or
                                (payload.role is not None and payload.role != RoleName.ADMIN)):
        raise HTTPException(status_code=400, detail="You cannot deactivate or demote your own account")

    if "full_name" in data and payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.role is not None and payload.role.value != user.role_name:
        old = user.role_name
        user.role = db.scalar(select(Role).where(Role.name == payload.role.value))
        audit(db, "ROLE_CHANGED", user_id=admin.id, entity_type="User", entity_id=user.id, ip=ip,
              details=f"{user.email}: {old} -> {payload.role.value}")
        security_event(db, "ROLE_CHANGED", "High",
                       f"{admin.email} changed {user.email} from {old} to {payload.role.value}",
                       user_id=admin.id, ip=ip)

    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        if payload.is_active:
            user.failed_login_count = 0
            user.locked_until = None
        audit(db, "ACCOUNT_ACTIVATED" if payload.is_active else "ACCOUNT_DEACTIVATED", user_id=admin.id,
              entity_type="User", entity_id=user.id, ip=ip, details=user.email)

    db.commit()
    db.refresh(user)
    return UserOut.from_user(user)
