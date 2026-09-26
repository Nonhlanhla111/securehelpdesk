"""Reusable FastAPI dependencies: authentication and role-based access control."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.database import get_db
from app.models import RevokedToken, User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Not authenticated",
                         headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate the bearer token, then load the user FRESH from the database.

    The role and active flag are read from the DB on every request (not from the
    token), so deactivating a user or changing a role takes effect immediately.
    """
    if creds is None:
        raise _unauthorized()
    payload = decode_access_token(creds.credentials)
    if payload is None or db.get(RevokedToken, payload["jti"]) is not None:
        raise _unauthorized()
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.token_version != payload["ver"]:
        raise _unauthorized()
    request.state.token_payload = payload
    return user


def require_roles(*allowed: str):
    """Dependency factory: only users whose role is in `allowed` may proceed."""

    def checker(request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> User:
        if user.role_name not in allowed:
            ip = client_ip(request)
            desc = f"{user.email} ({user.role_name}) tried {request.method} {request.url.path}"
            audit(db, "UNAUTHORIZED_ACCESS", user_id=user.id, ip=ip, details=desc)
            security_event(db, "UNAUTHORIZED_ACCESS", "Medium", desc, user_id=user.id, ip=ip)
            db.commit()  # commit before raising, otherwise the log rows would be rolled back
            raise HTTPException(status_code=403, detail="You do not have permission to do that")
        return user

    return checker
