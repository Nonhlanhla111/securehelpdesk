"""Pydantic schemas: validate everything coming in, shape everything going out."""
import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import CategoryName, PriorityName, RoleName, StatusName

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # keeps \t \n \r


def _clean(v: str) -> str:
    v = v.strip()
    if _CONTROL.search(v):
        raise ValueError("contains invalid control characters")
    return v


# str that is trimmed and free of control characters (NUL bytes etc.)
CleanStr = Annotated[str, AfterValidator(_clean)]


def _check_password_strength(pw: str) -> str:
    if len(pw) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if len(pw) > 128:
        raise ValueError("Password must be at most 128 characters long")
    if not (re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw) and re.search(r"\d", pw)):
        raise ValueError("Password must contain upper-case, lower-case and a digit")
    return pw


StrongPassword = Annotated[str, AfterValidator(_check_password_strength)]


# ------------------------------------------------------------------- auth
class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: CleanStr = Field(min_length=2, max_length=100)
    password: StrongPassword


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: StrongPassword


class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------------------------ users
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None

    @classmethod
    def from_user(cls, u) -> "UserOut":
        return cls(id=u.id, email=u.email, full_name=u.full_name, role=u.role_name,
                   is_active=u.is_active, created_at=u.created_at, last_login_at=u.last_login_at)


class UserBrief(BaseModel):
    id: int
    full_name: str


class AdminCreateUser(BaseModel):
    email: EmailStr
    full_name: CleanStr = Field(min_length=2, max_length=100)
    password: StrongPassword
    role: RoleName = RoleName.EMPLOYEE


class UserUpdate(BaseModel):
    full_name: CleanStr | None = Field(default=None, min_length=2, max_length=100)
    role: RoleName | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------- tickets
class TicketCreate(BaseModel):
    title: CleanStr = Field(min_length=5, max_length=200)
    description: CleanStr = Field(min_length=10, max_length=5000)
    category: CategoryName
    priority: PriorityName = PriorityName.MEDIUM


class TicketUpdate(BaseModel):
    title: CleanStr | None = Field(default=None, min_length=5, max_length=200)
    description: CleanStr | None = Field(default=None, min_length=10, max_length=5000)
    category: CategoryName | None = None
    priority: PriorityName | None = None
    status: StatusName | None = None

    @field_validator("title", "description", "category", "priority", "status")
    @classmethod
    def not_null_if_sent(cls, v):
        if v is None:
            raise ValueError("must not be null")
        return v


class AssignRequest(BaseModel):
    agent_id: int | None = None  # omit to assign to yourself (agents)


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    priority: str
    status: str
    created_by_id: int
    created_by_name: str
    assigned_to_id: int | None
    assigned_to_name: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_ticket(cls, t) -> "TicketOut":
        return cls(
            id=t.id, title=t.title, description=t.description, category=t.category.name,
            priority=t.priority.name, status=t.status.name, created_by_id=t.created_by_id,
            created_by_name=t.created_by.full_name, assigned_to_id=t.assigned_to_id,
            assigned_to_name=t.assigned_to.full_name if t.assigned_to else None,
            created_at=t.created_at, updated_at=t.updated_at, resolved_at=t.resolved_at,
        )


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class TicketPage(Page):
    items: list[TicketOut]


class CommentCreate(BaseModel):
    body: CleanStr = Field(min_length=1, max_length=5000)
    is_internal: bool = False  # staff-only investigation note


class CommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    author_name: str
    author_role: str
    body: str
    is_internal: bool
    created_at: datetime

    @classmethod
    def from_comment(cls, c) -> "CommentOut":
        return cls(id=c.id, ticket_id=c.ticket_id, author_id=c.author_id, author_name=c.author.full_name,
                   author_role=c.author.role_name, body=c.body, is_internal=c.is_internal,
                   created_at=c.created_at)


class HistoryOut(BaseModel):
    id: int
    ticket_id: int
    changed_by_id: int
    changed_by_name: str
    field: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int
    uploaded_by_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


# ------------------------------------------------------------ logs/events
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    user_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    ip_address: str | None
    details: str | None


class SecurityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    event_type: str
    severity: str
    user_id: int | None
    ip_address: str | None
    description: str
