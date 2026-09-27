import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Loading, EmptyState, formatDateTime } from "../components/Loading";
import { SeverityDot } from "../components/Chips";

export default function AdminLogs() {
  const [tab, setTab] = useState("audit");

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Audit &amp; Security</h1>
          <p>A record of important actions and events that may indicate suspicious activity.</p>
        </div>
      </div>

      <div className="tab-bar">
        <button className={`tab-btn${tab === "audit" ? " active" : ""}`} onClick={() => setTab("audit")}>Audit log</button>
        <button className={`tab-btn${tab === "security" ? " active" : ""}`} onClick={() => setTab("security")}>Security events</button>
      </div>

      {tab === "audit" ? <AuditTable /> : <SecurityTable />}
    </div>
  );
}

function AuditTable() {
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    api.get("/api/audit-logs", { params: { page_size: 100 } }).then((res) => {
      setItems(res.data.items);
      setTotal(res.data.total);
    });
  }, []);

  if (!items) return <Loading />;

  return (
    <div className="panel">
      {items.length === 0 && <EmptyState title="No audit log entries yet" />}
      {items.length > 0 && (
        <table className="data-table">
          <thead>
            <tr><th>Time</th><th>Action</th><th>User</th><th>IP</th><th>Details</th></tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{formatDateTime(a.timestamp)}</td>
                <td>{a.action}</td>
                <td>{a.user_id ?? "—"}</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{a.ip_address || "—"}</td>
                <td style={{ color: "var(--muted)" }}>{a.details || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pagination">Showing {items.length} of {total} entries</div>
    </div>
  );
}

function SecurityTable() {
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    api.get("/api/security-events", { params: { page_size: 100 } }).then((res) => {
      setItems(res.data.items);
      setTotal(res.data.total);
    });
  }, []);

  if (!items) return <Loading />;

  return (
    <div className="panel">
      {items.length === 0 && <EmptyState title="No security events recorded" hint="That's good news." />}
      {items.length > 0 && (
        <table className="data-table">
          <thead>
            <tr><th>Time</th><th>Type</th><th>Severity</th><th>User</th><th>IP</th><th>Description</th></tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id}>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{formatDateTime(e.timestamp)}</td>
                <td>{e.event_type}</td>
                <td><SeverityDot severity={e.severity} />{e.severity}</td>
                <td>{e.user_id ?? "—"}</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{e.ip_address || "—"}</td>
                <td style={{ color: "var(--muted)" }}>{e.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pagination">Showing {items.length} of {total} events</div>
    </div>
  );
}
