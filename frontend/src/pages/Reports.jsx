import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Loading } from "../components/Loading";

export default function Reports() {
  const [data, setData] = useState(null);
  const [range, setRange] = useState(30);

  useEffect(() => {
    const to = new Date();
    const from = new Date(to.getTime() - range * 86400000);
    api.get("/api/reports/summary", {
      params: { date_from: from.toISOString().slice(0, 10), date_to: to.toISOString().slice(0, 10) },
    }).then((res) => setData(res.data));
  }, [range]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Reports</h1>
          <p>Help desk activity for the selected period.</p>
        </div>
        <select value={range} onChange={(e) => setRange(Number(e.target.value))}>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {!data && <Loading />}
      {data && (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-value">{data.tickets_created}</div>
              <div className="stat-label">Tickets created</div>
            </div>
            <div className="stat-card accent-primary">
              <div className="stat-value">{data.tickets_resolved}</div>
              <div className="stat-label">Tickets resolved</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{data.open_vs_closed.closed}</div>
              <div className="stat-label">Closed</div>
            </div>
            <div className="stat-card accent-amber">
              <div className="stat-value">{data.open_vs_closed.not_closed}</div>
              <div className="stat-label">Still open</div>
            </div>
          </div>

          <div className="detail-grid">
            <BreakdownPanel title="By category" data={data.by_category} />
            <BreakdownPanel title="By priority" data={data.by_priority} />
          </div>
          <div className="detail-grid" style={{ marginTop: 14 }}>
            <BreakdownPanel title="By status" data={data.by_status} />
            <BreakdownPanel title="Assigned per agent" data={data.assigned_per_agent} empty="No assignments in this period." />
          </div>
          {data.security_events_by_type && (
            <div className="panel" style={{ marginTop: 14 }}>
              <div className="panel-header"><h2>Security events by type</h2></div>
              <div className="panel-body">
                <BreakdownRows data={data.security_events_by_type} empty="No security events in this period." />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function BreakdownPanel({ title, data, empty }) {
  return (
    <div className="panel">
      <div className="panel-header"><h2>{title}</h2></div>
      <div className="panel-body">
        <BreakdownRows data={data} empty={empty} />
      </div>
    </div>
  );
}

function BreakdownRows({ data, empty = "No data in this period." }) {
  const entries = Object.entries(data || {});
  if (entries.length === 0) return <p style={{ color: "var(--muted)", fontSize: 13 }}>{empty}</p>;
  const max = Math.max(...entries.map(([, n]) => n));
  return (
    <div>
      {entries.map(([label, count]) => (
        <div key={label} style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
            <span>{label}</span><strong>{count}</strong>
          </div>
          <div style={{ background: "var(--surface-sunken)", borderRadius: 4, height: 6 }}>
            <div style={{ width: `${(count / max) * 100}%`, background: "var(--primary)", height: 6, borderRadius: 4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
