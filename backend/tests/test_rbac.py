import pytest
from sqlalchemy import select

from app.models import AuditLog, SecurityEvent

ADMIN_ONLY = [("get", "/api/users"), ("get", "/api/audit-logs"), ("get", "/api/security-events"),
              ("get", "/api/users/1")]


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
@pytest.mark.parametrize("role", ["emp", "agent"])
def test_admin_endpoints_forbidden_for_other_roles(client, h, role, method, path):
    assert getattr(client, method)(path, headers=h[role]).status_code == 403


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_admin_endpoints_need_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_admin_endpoints_work_for_admin(client, h):
    for _, path in ADMIN_ONLY:
        assert client.get(path, headers=h["admin"]).status_code == 200


def test_forbidden_attempt_is_logged(client, h, users, db):
    client.get("/api/users", headers=h["emp"])
    ev = db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "UNAUTHORIZED_ACCESS"))
    assert ev and ev.user_id == users["emp"].id
    assert db.scalar(select(AuditLog).where(AuditLog.action == "UNAUTHORIZED_ACCESS"))


def test_employee_cannot_escalate_own_role(client, h, users):
    r = client.put(f"/api/users/{users['emp'].id}", json={"role": "Administrator"}, headers=h["emp"])
    assert r.status_code == 403
    assert client.get("/api/auth/me", headers=h["emp"]).json()["role"] == "Employee"


def test_admin_role_change_is_high_severity_event(client, h, users, db):
    r = client.put(f"/api/users/{users['emp'].id}", json={"role": "IT Support Agent"}, headers=h["admin"])
    assert r.status_code == 200 and r.json()["role"] == "IT Support Agent"
    ev = db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "ROLE_CHANGED"))
    assert ev.severity == "High"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "ROLE_CHANGED"))


def test_role_change_takes_effect_immediately_on_existing_token(client, h, users):
    client.put(f"/api/users/{users['emp'].id}", json={"role": "IT Support Agent"}, headers=h["admin"])
    assert client.get("/api/auth/me", headers=h["emp"]).json()["role"] == "IT Support Agent"


def test_admin_cannot_demote_or_deactivate_self(client, h, users):
    assert client.put(f"/api/users/{users['admin'].id}", json={"role": "Employee"},
                      headers=h["admin"]).status_code == 400
    assert client.put(f"/api/users/{users['admin'].id}", json={"is_active": False},
                      headers=h["admin"]).status_code == 400


def test_admin_creates_agent_account(client, h):
    r = client.post("/api/users", headers=h["admin"], json={
        "email": "newagent@example.com", "full_name": "New Agent",
        "password": "Str0ngPassw0rd!", "role": "IT Support Agent"})
    assert r.status_code == 201 and r.json()["role"] == "IT Support Agent"


def test_user_list_filters_and_pagination(client, h):
    r = client.get("/api/users", params={"role": "Employee", "page_size": 1}, headers=h["admin"]).json()
    assert r["total"] == 2 and len(r["items"]) == 1


def test_agents_list_available_to_staff_not_employees(client, h):
    assert client.get("/api/users/agents", headers=h["agent"]).status_code == 200
    assert client.get("/api/users/agents", headers=h["emp"]).status_code == 403
    names = [a["full_name"] for a in client.get("/api/users/agents", headers=h["admin"]).json()]
    assert "Aisha Agent" in names and "Ella Employee" not in names
