import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading, EmptyState, formatDateTime } from "../components/Loading";
import { PriorityChip, StatusChip } from "../components/Chips";
import { IconSearch } from "../components/Icons";

const STATUSES = ["Open", "Assigned", "In Progress", "Resolved", "Closed"];
const CATEGORIES = ["Hardware", "Software", "Network", "Account Access", "Security", "Email", "System Issues", "Other"];
const PRIORITIES = ["Low", "Medium", "High", "Critical"];
const PAGE_SIZE = 15;

export default function TicketList() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isStaff = user.role !== "Employee";

  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState("");
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [page, setPage] = useState(1);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = { page, page_size: PAGE_SIZE };
    if (q.trim()) params.q = q.trim();
    if (status) params.status = status;
    if (category) params.category = category;
    if (priority) params.priority = priority;
    if (unassignedOnly) params.unassigned = true;

    const handle = setTimeout(() => {
      api.get("/api/tickets", { params }).then((res) => {
        setResult(res.data);
        setLoading(false);
      });
    }, 250); // debounce free-text search
    return () => clearTimeout(handle);
  }, [q, status, category, priority, unassignedOnly, page]);

  useEffect(() => setPage(1), [q, status, category, priority, unassignedOnly]);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Tickets</h1>
          <p>{isStaff ? "The shared queue plus anything assigned to you." : "IT issues you've reported."}</p>
        </div>
      </div>

      <div className="filters-bar">
        <div style={{ position: "relative", flex: "1 1 220px" }}>
          <IconSearch width={14} height={14} style={{ position: "absolute", left: 9, top: 9, color: "var(--muted)" }} />
          <input
            style={{ paddingLeft: 28, width: "100%" }}
            placeholder="Search by title or ticket #"
            value={q} onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Any category</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">Any priority</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {isStaff && (
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--ink-soft)" }}>
            <input type="checkbox" checked={unassignedOnly} onChange={(e) => setUnassignedOnly(e.target.checked)} />
            Unassigned only
          </label>
        )}
      </div>

      <div className="panel">
        {loading && <Loading />}
        {!loading && result && result.items.length === 0 && (
          <EmptyState title="No tickets match these filters" hint="Try clearing a filter, or create a new ticket." />
        )}
        {!loading && result && result.items.length > 0 && (
          <div className="ticket-list">
            {result.items.map((t) => (
              <div key={t.id} className="ticket-row" onClick={() => navigate(`/tickets/${t.id}`)}>
                <div className={`priority-bar ${t.priority}`} />
                <div className="ticket-main">
                  <div className="ticket-title">{t.title}</div>
                  <div className="ticket-meta">
                    <span className="ticket-id">#{t.id}</span>
                    <span>{t.category}</span>
                    {isStaff && <span>{t.created_by_name}</span>}
                    {t.assigned_to_name && <span>→ {t.assigned_to_name}</span>}
                  </div>
                </div>
                <PriorityChip priority={t.priority} />
                <StatusChip status={t.status} />
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{formatDateTime(t.updated_at)}</span>
              </div>
            ))}
          </div>
        )}
        {result && result.total > 0 && (
          <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span>Page {page} of {totalPages} · {result.total} tickets</span>
            <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        )}
      </div>
    </div>
  );
}
