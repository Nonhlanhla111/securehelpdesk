"""Register, login, logout, current user, change password."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.config import get_settings
from app.constants import RoleName
from app.database import get_db
from app.deps import get_current_user
from app.models import RevokedToken, Role, User, utcnow
from app.rate_limit import RateLimiter
from app.schemas import (ChangePasswordRequest, LoginRequest, MessageResponse,
                         RegisterRequest, TokenResponse, UserOut)
from app.security import (DUMMY_HASH, create_access_token, hash_password, verify_password)

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

login_limiter = RateLimiter("login", settings.login_rate_limit, settings.login_rate_window_seconds)
register_limiter = RateLimiter("register", settings.register_rate_limit, settings.register_rate_window_seconds)

INVALID_LOGIN = "Invalid email or password"  # same message for every failure reason


@router.post("/register", response_model=UserOut, status_code=201,
             dependencies=[Depends(register_limiter)])
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Self-registration. Always creates an *Employee* - roles can only be raised by an admin."""
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    role = db.scalar(select(Role).where(Role.name == RoleName.EMPLOYEE.value))
    user = User(email=email, full_name=payload.full_name, hashed_password=hash_password(payload.password),
                role_id=role.id)
    db.add(user)
    db.flush()
    audit(db, "ACCOUNT_CREATED", user_id=user.id, entity_type="User", entity_id=user.id,
          ip=client_ip(request), details="Self-registration")
    db.commit()
    db.refresh(user)
    return UserOut.from_user(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    now = utcnow()
    user = db.scalar(select(User).where(User.email == payload.email.lower()))

    # Locked out? (Only reveals lockout for real accounts after repeated failures - an accepted trade-off.)
    if user and user.locked_until and user.locked_until > now:
        audit(db, "LOGIN_BLOCKED", user_id=user.id, ip=ip, details="Account temporarily locked")
        db.commit()
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    # Always run one Argon2 verification so response time doesn't reveal whether the email exists.
    password_ok = verify_password(payload.password, user.hashed_password if user else DUMMY_HASH)

    if not user or not password_ok or not user.is_active:
        if user:
            user.failed_login_count += 1
            reason = "Wrong password" if not password_ok else "Account deactivated"
            audit(db, "LOGIN_FAILED", user_id=user.id, ip=ip, details=reason)
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
                security_event(db, "MULTIPLE_FAILED_LOGINS", "High",
                               f"{user.email}: {settings.max_failed_logins} failed logins; "
                               f"locked for {settings.lockout_minutes} minutes",
                               user_id=user.id, ip=ip)
        else:
            # Don't store the submitted email: users sometimes paste passwords into that field.
            audit(db, "LOGIN_FAILED", ip=ip, details="Unknown account")
        db.commit()
        raise HTTPException(status_code=401, detail=INVALID_LOGIN)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    token, _jti, _exp = create_access_token(user.id, user.token_version)
    audit(db, "LOGIN_SUCCESS", user_id=user.id, ip=ip)
    db.commit()
    return TokenResponse(access_token=token, expires_in=settings.access_token_expire_minutes * 60)


def _revoke_current_token(request: Request, db: Session) -> None:
    from datetime import datetime, timezone
    p = request.state.token_payload
    exp = datetime.fromtimestamp(p["exp"], tz=timezone.utc).replace(tzinfo=None)
    db.add(RevokedToken(jti=p["jti"], expires_at=exp))
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow()))  # tidy up expired rows


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _revoke_current_token(request, db)
    audit(db, "LOGOUT", user_id=user.id, ip=client_ip(request))
    db.commit()
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.from_user(user)


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not verify_password(payload.current_password, user.hashed_password):
        audit(db, "PASSWORD_CHANGE_FAILED", user_id=user.id, ip=ip, details="Wrong current password")
        security_event(db, "PASSWORD_CHANGE_FAILED", "Medium",
                       f"{user.email} supplied a wrong current password", user_id=user.id, ip=ip)
        db.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1  # invalidates every token issued before now, on every device
    audit(db, "PASSWORD_CHANGED", user_id=user.id, entity_type="User", entity_id=user.id, ip=ip)
    db.commit()
    return MessageResponse(message="Password changed. Please log in again.")
