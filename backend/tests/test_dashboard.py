from tests.conftest import new_ticket


def test_employee_dashboard(client, h):
    t = new_ticket(client, h["emp"])
    new_ticket(client, h["emp2"])
    d = client.get("/api/dashboard", headers=h["emp"]).json()
    assert d["role"] == "Employee" and d["open_tickets"] == 1 and d["in_progress"] == 0
    assert [x["id"] for x in d["recently_updated"]] == [t["id"]]


def test_agent_dashboard(client, h):
    t = new_ticket(client, h["emp"], priority="Critical")
    new_ticket(client, h["emp"], priority="High")
    client.post(f"/api/tickets/{t['id']}/assign", headers=h["agent"])
    client.put(f"/api/tickets/{t['id']}", json={"status": "In Progress"}, headers=h["agent"])
    d = client.get("/api/dashboard", headers=h["agent"]).json()
    assert d["assigned_to_me"] == 1 and d["critical"] == 1 and d["high_priority"] == 1
    assert d["awaiting_resolution"] == 1 and d["open_tickets"] == 1


def test_admin_dashboard(client, h):
    new_ticket(client, h["emp"], priority="Critical")
    client.get("/api/users", headers=h["emp"])  # forbidden -> creates a security event
    d = client.get("/api/dashboard", headers=h["admin"]).json()
    assert d["total_users"] == 5 and d["active_users"] == 5 and d["total_tickets"] == 1
    assert d["critical_tickets"] == 1 and d["security_events_24h"] >= 1
    assert d["recent_activity"] and d["recent_security_events"]


def test_reports_staff_only_and_security_section_admin_only(client, h):
    new_ticket(client, h["emp"], category="Hardware", priority="High")
    assert client.get("/api/reports/summary", headers=h["emp"]).status_code == 403
    agent = client.get("/api/reports/summary", headers=h["agent"]).json()
    assert agent["tickets_created"] == 1 and agent["by_category"] == {"Hardware": 1}
    assert agent["by_priority"] == {"High": 1} and "security_events_by_type" not in agent
    admin = client.get("/api/reports/summary", headers=h["admin"]).json()
    assert "security_events_by_type" in admin


def test_audit_log_filters(client, h, users):
    new_ticket(client, h["emp"])
    r = client.get("/api/audit-logs", params={"action": "TICKET_CREATED"}, headers=h["admin"]).json()
    assert r["total"] == 1 and r["items"][0]["user_id"] == users["emp"].id
    assert client.get("/api/security-events", params={"severity": "Nonsense"}, headers=h["admin"]).status_code == 422
