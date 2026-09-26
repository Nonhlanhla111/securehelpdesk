import pytest
from sqlalchemy import select

from app.models import AuditLog, SecurityEvent
from tests.conftest import new_ticket


# --------------------------------------------------------------- creation
def test_employee_creates_ticket_open_by_default(client, h, users):
    t = new_ticket(client, h["emp"])
    assert t["status"] == "Open" and t["priority"] == "Medium" and t["category"] == "Network"
    assert t["created_by_id"] == users["emp"].id and t["assigned_to_id"] is None


@pytest.mark.parametrize("bad", [
    {"title": "abc"}, {"description": "short"}, {"category": "Coffee Machine"},
    {"priority": "Urgent!!"}, {"title": "x" * 201}, {"title": "Null\x00byte title"},
])
def test_ticket_validation_rejects_bad_input(client, h, bad):
    body = {"title": "Valid title here", "description": "A valid long description.",
            "category": "Hardware", "priority": "Low"}
    body.update(bad)
    assert client.post("/api/tickets", json=body, headers=h["emp"]).status_code == 422


def test_ticket_endpoints_require_auth(client):
    assert client.get("/api/tickets").status_code == 401
    assert client.post("/api/tickets", json={}).status_code == 401


# ------------------------------------------------------------- visibility
def test_employee_sees_only_own_tickets(client, h):
    mine = new_ticket(client, h["emp"], title="My laptop is broken")
    new_ticket(client, h["emp2"], title="Someone else's problem")
    r = client.get("/api/tickets", headers=h["emp"]).json()
    assert [t["id"] for t in r["items"]] == [mine["id"]] and r["total"] == 1


def test_idor_employee_cannot_read_or_modify_other_users_ticket(client, h, db):
    victim = new_ticket(client, h["emp2"])
    tid = victim["id"]
    assert client.get(f"/api/tickets/{tid}", headers=h["emp"]).status_code == 404
    assert client.put(f"/api/tickets/{tid}", json={"title": "Hacked title!"}, headers=h["emp"]).status_code == 404
    assert client.get(f"/api/tickets/{tid}/comments", headers=h["emp"]).status_code == 404
    assert client.post(f"/api/tickets/{tid}/comments", json={"body": "hi"}, headers=h["emp"]).status_code == 404
    assert client.get(f"/api/tickets/{tid}/attachments", headers=h["emp"]).status_code == 404
    events = db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "UNAUTHORIZED_ACCESS")).all()
    assert len(events) >= 5  # every probe was recorded
    assert client.get(f"/api/tickets/{tid}", headers=h["emp2"]).json()["title"] == victim["title"]


def test_nonexistent_and_forbidden_look_identical(client, h):
    other = new_ticket(client, h["emp2"])
    a = client.get(f"/api/tickets/{other['id']}", headers=h["emp"])
    b = client.get("/api/tickets/999999", headers=h["emp"])
    assert a.status_code == b.status_code == 404 and a.json() == b.json()


def test_agent_sees_queue_and_own_but_not_other_agents_tickets(client, h):
    t = new_ticket(client, h["emp"])
    assert client.get(f"/api/tickets/{t['id']}", headers=h["agent"]).status_code == 200  # unassigned queue
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    assert client.get(f"/api/tickets/{t['id']}", headers=h["agent2"]).status_code == 404
    assert t["id"] not in [x["id"] for x in client.get("/api/tickets", headers=h["agent2"]).json()["items"]]
    assert client.get(f"/api/tickets/{t['id']}", headers=h["admin"]).status_code == 200


# ---------------------------------------------------------------- workflow
def test_full_lifecycle_open_to_closed(client, h, users):
    t = new_ticket(client, h["emp"])
    tid = t["id"]
    r = client.post(f"/api/tickets/{tid}/assign", headers=h["agent"])
    assert r.status_code == 200 and r.json()["status"] == "Assigned"
    assert r.json()["assigned_to_id"] == users["agent"].id
    assert client.put(f"/api/tickets/{tid}", json={"status": "In Progress"}, headers=h["agent"]).json()["status"] == "In Progress"
    r = client.put(f"/api/tickets/{tid}", json={"status": "Resolved"}, headers=h["agent"]).json()
    assert r["status"] == "Resolved" and r["resolved_at"] is not None
    r = client.put(f"/api/tickets/{tid}", json={"status": "Closed"}, headers=h["emp"])  # employee confirms
    assert r.status_code == 200 and r.json()["status"] == "Closed"
    hist = client.get(f"/api/tickets/{tid}/history", headers=h["agent"]).json()
    assert [(x["field"], x["new_value"]) for x in hist] == [
        ("created", "Open"), ("assigned_to", "Aisha Agent"), ("status", "Assigned"),
        ("status", "In Progress"), ("status", "Resolved"), ("status", "Closed")]


@pytest.mark.parametrize("bad_status", ["Closed", "Resolved", "Assigned", "Open"])
def test_invalid_status_jumps_rejected(client, h, bad_status):
    t = new_ticket(client, h["emp"])
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    r = client.put(f"/api/tickets/{t['id']}", json={"status": bad_status}, headers=h["agent"])
    assert r.status_code == 400


def test_agent_cannot_update_ticket_before_accepting_it(client, h):
    t = new_ticket(client, h["emp"])
    r = client.put(f"/api/tickets/{t['id']}", json={"priority": "High"}, headers=h["agent"])
    assert r.status_code == 403


def test_employee_can_reject_resolution(client, h):
    t = new_ticket(client, h["emp"])
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    client.put(f"/api/tickets/{t['id']}", json={"status": "In Progress"}, headers=h["agent"])
    client.put(f"/api/tickets/{t['id']}", json={"status": "Resolved"}, headers=h["agent"])
    r = client.put(f"/api/tickets/{t['id']}", json={"status": "In Progress"}, headers=h["emp"])
    assert r.status_code == 200 and r.json()["status"] == "In Progress" and r.json()["resolved_at"] is None


def test_employee_cannot_change_priority_category_or_skip_status(client, h, db):
    t = new_ticket(client, h["emp"])
    for body in ({"priority": "Critical"}, {"category": "Security"}):
        assert client.put(f"/api/tickets/{t['id']}", json=body, headers=h["emp"]).status_code == 403
    assert client.put(f"/api/tickets/{t['id']}", json={"status": "Closed"}, headers=h["emp"]).status_code == 400
    assert client.get(f"/api/tickets/{t['id']}", headers=h["emp"]).json()["priority"] == "Medium"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "UNAUTHORIZED_ACCESS"))


def test_employee_can_edit_title_while_open_only(client, h):
    t = new_ticket(client, h["emp"])
    assert client.put(f"/api/tickets/{t['id']}", json={"title": "Better title now"}, headers=h["emp"]).json()["title"] == "Better title now"
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    assert client.put(f"/api/tickets/{t['id']}", json={"title": "Changed again!"}, headers=h["emp"]).status_code == 409


def test_agent_changes_priority_and_history_records_it(client, h):
    t = new_ticket(client, h["emp"])
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    r = client.put(f"/api/tickets/{t['id']}", json={"priority": "Critical"}, headers=h["agent"])
    assert r.json()["priority"] == "Critical"
    hist = client.get(f"/api/tickets/{t['id']}/history", headers=h["agent"]).json()
    assert ("priority", "Medium", "Critical") in [(x["field"], x["old_value"], x["new_value"]) for x in hist]


def test_null_and_empty_updates_rejected(client, h):
    t = new_ticket(client, h["emp"])
    assert client.put(f"/api/tickets/{t['id']}", json={}, headers=h["emp"]).status_code == 400
    assert client.put(f"/api/tickets/{t['id']}", json={"title": None}, headers=h["emp"]).status_code == 422


def test_closed_ticket_is_read_only(client, h):
    t = new_ticket(client, h["emp"])
    tid = t["id"]
    client.post(f"/api/tickets/{tid}/assign", headers=h["agent"])
    for s in ("In Progress", "Resolved"):
        client.put(f"/api/tickets/{tid}", json={"status": s}, headers=h["agent"])
    client.put(f"/api/tickets/{tid}", json={"status": "Closed"}, headers=h["emp"])
    assert client.put(f"/api/tickets/{tid}", json={"priority": "Low"}, headers=h["admin"]).status_code == 409
    assert client.post(f"/api/tickets/{tid}/comments", json={"body": "hello"}, headers=h["emp"]).status_code == 409


# ------------------------------------------------------------- assignment
def test_agent_cannot_assign_to_someone_else_or_take_taken_ticket(client, h, users):
    t = new_ticket(client, h["emp"])
    r = client.post(f"/api/tickets/{t['id']}/assign", json={"agent_id": users["agent2"].id}, headers=h["agent"])
    assert r.status_code == 403
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    assert client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent2"]).status_code == 404  # not visible to them


def test_admin_assigns_to_agent_but_not_to_employee(client, h, users):
    t = new_ticket(client, h["emp"])
    ok = client.post(f"/api/tickets/{t['id']}/assign", json={"agent_id": users["agent2"].id}, headers=h["admin"])
    assert ok.status_code == 200 and ok.json()["assigned_to_name"] == "Pieter Agent"
    bad = client.post(f"/api/tickets/{t['id']}/assign", json={"agent_id": users["emp"].id}, headers=h["admin"])
    assert bad.status_code == 400


def test_employee_cannot_assign(client, h):
    t = new_ticket(client, h["emp"])
    assert client.post(f"/api/tickets/{t['id']}/assign", headers=h["emp"]).status_code == 403


def test_only_admin_can_delete(client, h):
    t = new_ticket(client, h["emp"])
    assert client.delete(f"/api/tickets/{t['id']}", headers=h["emp"]).status_code == 403
    assert client.delete(f"/api/tickets/{t['id']}", headers=h["agent"]).status_code == 403
    assert client.delete(f"/api/tickets/{t['id']}", headers=h["admin"]).status_code == 204
    assert client.get(f"/api/tickets/{t['id']}", headers=h["admin"]).status_code == 404


# --------------------------------------------------------------- comments
def test_comments_thread_and_internal_notes_hidden_from_employee(client, h):
    t = new_ticket(client, h["emp"])
    tid = t["id"]
    client.post(f"/api/tickets/{tid}/assign", headers=h["agent"])
    assert client.post(f"/api/tickets/{tid}/comments", json={"body": "Have you tried a reboot?"}, headers=h["agent"]).status_code == 201
    assert client.post(f"/api/tickets/{tid}/comments", json={"body": "Rebooted, still failing."}, headers=h["emp"]).status_code == 201
    assert client.post(f"/api/tickets/{tid}/comments", json={"body": "Looks like a rogue DHCP scope.", "is_internal": True}, headers=h["agent"]).status_code == 201
    emp_view = client.get(f"/api/tickets/{tid}/comments", headers=h["emp"]).json()
    agent_view = client.get(f"/api/tickets/{tid}/comments", headers=h["agent"]).json()
    assert len(emp_view) == 2 and len(agent_view) == 3
    assert not any(c["is_internal"] for c in emp_view)
    assert [c["author_role"] for c in emp_view] == ["IT Support Agent", "Employee"]


def test_employee_cannot_post_internal_note(client, h):
    t = new_ticket(client, h["emp"])
    r = client.post(f"/api/tickets/{t['id']}/comments", json={"body": "secret", "is_internal": True}, headers=h["emp"])
    assert r.status_code == 403


def test_history_is_staff_only(client, h):
    t = new_ticket(client, h["emp"])
    assert client.get(f"/api/tickets/{t['id']}/history", headers=h["emp"]).status_code == 403


# --------------------------------------------------- search & filtering
def test_search_and_filters(client, h):
    a = new_ticket(client, h["emp"], title="Printer on floor 3 jammed", category="Hardware", priority="High")
    b = new_ticket(client, h["emp2"], title="VPN drops every hour", category="Network", priority="Low")
    g = lambda **p: [t["id"] for t in client.get("/api/tickets", params=p, headers=h["admin"]).json()["items"]]  # noqa: E731
    assert g(q="printer") == [a["id"]]
    assert g(q=str(b["id"])) == [b["id"]]                       # search by ticket ID
    assert g(category="Network") == [b["id"]]
    assert g(priority="High") == [a["id"]]
    assert g(status="Open") == [b["id"], a["id"]] or set(g(status="Open")) == {a["id"], b["id"]}
    assert g(employee="sipho") == [b["id"]]
    assert g(unassigned="true") and g(assigned_to_id=999) == []
    assert g(created_from="2999-01-01") == []
    assert set(g(created_from="2000-01-01", created_to="2999-12-31")) == {a["id"], b["id"]}


def test_filters_cannot_widen_visibility(client, h, users):
    new_ticket(client, h["emp2"])
    r = client.get("/api/tickets", params={"employee": "sipho", "created_by_id": users["emp2"].id}, headers=h["emp"])
    assert r.json()["total"] == 0


def test_pagination_and_bounds(client, h):
    for i in range(5):
        new_ticket(client, h["emp"], title=f"Ticket number {i} broken")
    r = client.get("/api/tickets", params={"page_size": 2, "page": 3}, headers=h["emp"]).json()
    assert r["total"] == 5 and len(r["items"]) == 1
    assert client.get("/api/tickets", params={"page_size": 100000}, headers=h["emp"]).status_code == 422
    assert client.get("/api/tickets", params={"page": 0}, headers=h["emp"]).status_code == 422


# ------------------------------------------------ injection / XSS safety
SQLI = ["' OR '1'='1", "'; DROP TABLE tickets;--", "1; SELECT * FROM users", "%' OR 1=1 --", "\" OR \"\"=\""]


@pytest.mark.parametrize("payload", SQLI)
def test_sql_injection_in_search_and_filters_is_inert(client, h, payload):
    new_ticket(client, h["emp"])
    r = client.get("/api/tickets", params={"q": payload, "employee": payload}, headers=h["admin"])
    assert r.status_code == 200 and r.json()["total"] == 0  # treated as literal text, not SQL
    assert client.get("/api/tickets", headers=h["admin"]).json()["total"] == 1  # table still there


@pytest.mark.parametrize("payload", SQLI)
def test_sql_injection_in_login_fails_cleanly(client, users, payload):
    r = client.post("/api/auth/login", json={"email": payload, "password": payload})
    assert r.status_code == 422  # not a valid email at all


def test_like_wildcards_are_escaped(client, h):
    new_ticket(client, h["emp"], title="100% disk usage on server")
    new_ticket(client, h["emp"], title="Slow computer overall")
    r = client.get("/api/tickets", params={"q": "%"}, headers=h["admin"]).json()
    assert r["total"] == 1  # a bare % must NOT match everything


def test_xss_payload_stored_verbatim_as_json_text(client, h):
    xss = "<script>alert('xss')</script>"
    t = new_ticket(client, h["emp"], title=xss + " title")
    r = client.get(f"/api/tickets/{t['id']}", headers=h["emp"])
    assert r.headers["content-type"].startswith("application/json")  # never served as HTML
    assert r.json()["title"].startswith(xss)  # React escapes on render; we don't corrupt data on input
    assert r.headers["x-content-type-options"] == "nosniff"


def test_unhandled_errors_do_not_leak_details(client, h, monkeypatch):
    from app.routers import tickets
    def boom(*a, **k): raise RuntimeError("secret internal detail: db password=hunter2")
    monkeypatch.setattr(tickets, "lookup_id", boom)
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app, raise_server_exceptions=False).post(
        "/api/tickets", headers=h["emp"],
        json={"title": "Valid title here", "description": "A valid description.", "category": "Other"})
    assert r.status_code == 500 and "hunter2" not in r.text and r.json() == {"detail": "Internal server error"}
