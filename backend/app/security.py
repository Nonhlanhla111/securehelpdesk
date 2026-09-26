"""Password hashing (Argon2id) and JWT creation/verification."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()  # Argon2id with library defaults

# Verified against when the email doesn't exist, so "unknown user" and
# "wrong password" take about the same time (prevents user enumeration by timing).
DUMMY_HASH = _hasher.hash("timing-equaliser-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, token_version: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expiry as naive UTC)."""
    jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "jti": jti, "ver": token_version, "iat": now, "exp": exp}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, exp.replace(tzinfo=None)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],  # never trust the token's own "alg" header
            options={"require": ["exp", "sub", "jti", "ver"]},
        )
        int(payload["sub"])
        return payload
    except (jwt.PyJWTError, ValueError):
        return None
