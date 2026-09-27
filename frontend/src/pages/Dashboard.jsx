import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading, EmptyState, formatDateTime } from "../components/Loading";
import { PriorityChip, StatusChip, SeverityDot } from "../components/Chips";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/api/dashboard").then((res) => setData(res.data));
  }, []);

  if (!data) return <Loading />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Welcome back, {user.full_name.split(" ")[0]}</h1>
          <p>Here's what's happening with the help desk right now.</p>
        </div>
      </div>

      {data.role === "Employee" && <EmployeeStats data={data} />}
      {data.role === "IT Support Agent" && <AgentStats data={data} />}
      {data.role === "Administrator" && <AdminStats data={data} />}

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header"><h2>Recently updated tickets</h2></div>
        <div className="ticket-list">
          {(data.recently_updated || []).length === 0 && (
            <EmptyState title="No tickets yet" hint="Recently updated tickets will show up here." />
          )}
          {(data.recently_updated || []).map((t) => (
            <div key={t.id} className="ticket-row" onClick={() => navigate(`/tickets/${t.id}`)}>
              <div className={`priority-bar ${t.priority}`} />
              <div className="ticket-main">
                <div className="ticket-title">{t.title}</div>
                <div className="ticket-meta">
                  <span className="ticket-id">#{t.id}</span>
                  <span>{t.category}</span>
                </div>
              </div>
              <PriorityChip priority={t.priority} />
              <StatusChip status={t.status} />
              <span style={{ fontSize: 12, color: "var(--muted)" }}>{formatDateTime(t.updated_at)}</span>
            </div>
          ))}
        </div>
      </div>

      {data.role === "Administrator" && <AdminActivity data={data} />}
    </div>
  );
}

function Stat({ value, label, accent }) {
  return (
    <div className={`stat-card${accent ? ` accent-${accent}` : ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function EmployeeStats({ data }) {
  return (
    <div className="stat-grid">
      <Stat value={data.open_tickets} label="Open" accent="primary" />
      <Stat value={data.in_progress} label="In progress" accent="amber" />
      <Stat value={data.resolved} label="Resolved" />
    </div>
  );
}

function AgentStats({ data }) {
  return (
    <div className="stat-grid">
      <Stat value={data.open_tickets} label="Open (queue)" accent="primary" />
      <Stat value={data.assigned_to_me} label="Assigned to me" />
      <Stat value={data.awaiting_resolution} label="Awaiting resolution" accent="amber" />
      <Stat value={data.high_priority} label="High priority" accent="amber" />
      <Stat value={data.critical} label="Critical" accent="red" />
    </div>
  );
}

function AdminStats({ data }) {
  return (
    <div className="stat-grid">
      <Stat value={data.total_users} label="Total users" />
      <Stat value={data.active_users} label="Active users" />
      <Stat value={data.total_tickets} label="Total tickets" accent="primary" />
      <Stat value={data.open_tickets} label="Open tickets" />
      <Stat value={data.critical_tickets} label="Critical tickets" accent="red" />
      <Stat value={data.security_events_24h} label="Security events (24h)" accent="amber" />
    </div>
  );
}

function AdminActivity({ data }) {
  return (
    <div className="detail-grid" style={{ marginTop: 20 }}>
      <div className="panel">
        <div className="panel-header"><h2>Recent activity</h2></div>
        <div className="panel-body" style={{ paddingTop: 4 }}>
          {(data.recent_activity || []).map((a) => (
            <div key={a.id} className="history-item">
              <span className="history-time">{formatDateTime(a.timestamp)}</span>
              <span>{a.action}{a.details ? ` — ${a.details}` : ""}</span>
            </div>
          ))}
          {(data.recent_activity || []).length === 0 && <p style={{ color: "var(--muted)" }}>No activity yet.</p>}
        </div>
      </div>
      <div className="panel">
        <div className="panel-header"><h2>Security events</h2></div>
        <div className="panel-body" style={{ paddingTop: 4 }}>
          {(data.recent_security_events || []).map((e) => (
            <div key={e.id} className="history-item">
              <span className="history-time">{formatDateTime(e.timestamp)}</span>
              <span><SeverityDot severity={e.severity} />{e.event_type}</span>
            </div>
          ))}
          {(data.recent_security_events || []).length === 0 && <p style={{ color: "var(--muted)" }}>No security events yet.</p>}
        </div>
      </div>
    </div>
  );
}
