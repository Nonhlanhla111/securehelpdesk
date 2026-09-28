from sqlalchemy import select

from app.models import AuditLog, SecurityEvent, User
from tests.conftest import PASSWORD, login, make_user


def test_register_creates_employee_and_hashes_password(client, db):
    r = client.post("/api/auth/register", json={"email": "New@Example.com", "full_name": "Nomvula Dlamini-Zoë",
                                                "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "Employee" and body["email"] == "new@example.com"
    assert "password" not in str(body).lower()
    user = db.scalar(select(User).where(User.email == "new@example.com"))
    assert user.hashed_password != PASSWORD and user.hashed_password.startswith("$argon2id$")
    assert user.full_name == "Nomvula Dlamini-Zoë"


def test_register_cannot_choose_role(client):
    r = client.post("/api/auth/register", json={"email": "sneaky@example.com", "full_name": "Sneaky Person",
                                                "password": PASSWORD, "role": "Administrator"})
    assert r.status_code == 201 and r.json()["role"] == "Employee"  # extra field ignored


def test_register_duplicate_email(client, users):
    r = client.post("/api/auth/register", json={"email": "emp@example.com", "full_name": "Dup User",
                                                "password": PASSWORD})
    assert r.status_code == 409


def test_weak_password_rejected_and_not_echoed(client):
    r = client.post("/api/auth/register", json={"email": "a@example.com", "full_name": "Weak Pass",
                                                "password": "short1A"})
    assert r.status_code == 422
    assert "short1A" not in r.text  # validation errors must not leak the submitted password


def test_login_success_and_me(client, users):
    headers = login(client, "emp@example.com")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200 and r.json()["email"] == "emp@example.com"


def test_login_failure_is_generic(client, users):
    wrong_pw = client.post("/api/auth/login", json={"email": "emp@example.com", "password": "Wrong-Passw0rd"})
    no_user = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Wrong-Passw0rd"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()  # can't tell "no such user" from "bad password"


def test_lockout_after_repeated_failures_logs_security_event(client, users, db):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "emp@example.com", "password": "Nope-Passw0rd"}
                           ).status_code == 401
    # Even the CORRECT password is refused while locked.
    r = client.post("/api/auth/login", json={"email": "emp@example.com", "password": PASSWORD})
    assert r.status_code == 429
    ev = db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "MULTIPLE_FAILED_LOGINS")).all()
    assert len(ev) == 1 and ev[0].severity == "High" and ev[0].user_id == users["emp"].id


def test_failed_logins_audited_without_storing_submitted_email(client, users, db):
    client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Nope-Passw0rd"})
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "LOGIN_FAILED")).all()
    assert rows and all("ghost" not in (r.details or "") for r in rows)


def test_deactivated_user_cannot_login(client, db):
    make_user(db, "gone@example.com", active=False)
    r = client.post("/api/auth/login", json={"email": "gone@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_login_rate_limit_per_ip(client, users, db):
    codes = [client.post("/api/auth/login", json={"email": f"x{i}@example.com", "password": "Nope-Passw0rd"}
                         ).status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    assert db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "RATE_LIMIT_EXCEEDED"))


def test_logout_revokes_token(client, users):
    headers = login(client, "emp@example.com")
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_no_token_and_garbage_token_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_tampered_or_alg_none_token_rejected(client, users):
    import base64, json
    def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '5', 'jti': 'x', 'ver': 0, 'exp': 9999999999})}."
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_change_password_invalidates_all_old_tokens(client, users):
    old = login(client, "emp@example.com")
    other_device = login(client, "emp@example.com")
    r = client.post("/api/auth/change-password", headers=old,
                    json={"current_password": PASSWORD, "new_password": "Br4ndNewPassword!"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert client.get("/api/auth/me", headers=other_device).status_code == 401
    login(client, "emp@example.com", "Br4ndNewPassword!")


def test_change_password_requires_correct_current(client, users, db):
    headers = login(client, "emp@example.com")
    r = client.post("/api/auth/change-password", headers=headers,
                    json={"current_password": "Wrong-Passw0rd", "new_password": "Br4ndNewPassword!"})
    assert r.status_code == 400
    assert db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "PASSWORD_CHANGE_FAILED"))


def test_deactivating_user_kills_existing_token(client, users, h):
    assert client.put(f"/api/users/{users['emp'].id}", json={"is_active": False},
                      headers=h["admin"]).status_code == 200
    assert client.get("/api/auth/me", headers=h["emp"]).status_code == 401


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_admin_bootstrap_creates_account_once(db):
    from app.seed import bootstrap_admin
    from app.models import User
    from sqlalchemy import select

    bootstrap_admin(db, "boot@example.com", "Boot Admin", PASSWORD)
    user = db.scalar(select(User).where(User.email == "boot@example.com"))
    assert user is not None and user.role_name == "Administrator"

    # Calling again (e.g. every app restart) must not touch the existing account.
    from app.security import hash_password
    original_hash = user.hashed_password
    bootstrap_admin(db, "boot@example.com", "Different Name", "SomeOtherPassw0rd!")
    db.refresh(user)
    assert user.hashed_password == original_hash and user.full_name == "Boot Admin"


def test_admin_bootstrap_noop_when_unset(db):
    from app.seed import bootstrap_admin
    from app.models import User
    from sqlalchemy import select

    bootstrap_admin(db, None, None, None)
    bootstrap_admin(db, "partial@example.com", None, None)
    assert db.scalar(select(User).where(User.email == "partial@example.com")) is None
