import os
import tempfile

# Configure BEFORE the app is imported: in-memory DB, throw-away upload folder.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="shd_uploads_")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256-0123456789"
os.environ["ENVIRONMENT"] = "development"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.routers.auth import login_limiter, register_limiter  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed import seed_lookups  # noqa: E402

# Argon2 is deliberately slow; use cheap parameters in tests only (production keeps the defaults).
from argon2 import PasswordHasher  # noqa: E402
from app import security as _security  # noqa: E402
_security._hasher = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)

PASSWORD = "Str0ngPassw0rd!"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_lookups(db)
    login_limiter.reset()
    register_limiter.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


def make_user(db, email, role="Employee", password=PASSWORD, name=None, active=True):
    r = db.scalar(select(Role).where(Role.name == role))
    u = User(email=email, full_name=name or email.split("@")[0].title(),
             hashed_password=hash_password(password), role_id=r.id, is_active=active)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def login(client, email, password=PASSWORD):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def users(db):
    """One user of each role."""
    return {
        "emp": make_user(db, "emp@example.com", "Employee", name="Ella Employee"),
        "emp2": make_user(db, "emp2@example.com", "Employee", name="Sipho Second"),
        "agent": make_user(db, "agent@example.com", "IT Support Agent", name="Aisha Agent"),
        "agent2": make_user(db, "agent2@example.com", "IT Support Agent", name="Pieter Agent"),
        "admin": make_user(db, "admin@example.com", "Administrator", name="Ada Admin"),
    }


@pytest.fixture
def h(client, users):
    """Auth headers per role."""
    return {k: login(client, u.email) for k, u in users.items()}


def new_ticket(client, headers, **over):
    body = {"title": "Cannot connect to Wi-Fi", "description": "Laptop fails to join the office network.",
            "category": "Network", "priority": "Medium"}
    body.update(over)
    r = client.post("/api/tickets", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
