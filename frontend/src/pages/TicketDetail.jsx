import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading, EmptyState, formatDateTime } from "../components/Loading";
import { PriorityChip, StatusChip } from "../components/Chips";
import { IconArrowLeft, IconPaperclip } from "../components/Icons";

// Mirrors the backend's allowed transitions (app/constants.py) so the UI only
// offers moves the API will actually accept.
const STAFF_TRANSITIONS = {
  Assigned: ["In Progress"],
  "In Progress": ["Resolved"],
  Resolved: ["Closed", "In Progress"],
};
const EMPLOYEE_TRANSITIONS = {
  Resolved: ["Closed", "In Progress"],
};

export default function TicketDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isStaff = user.role !== "Employee";

  const [ticket, setTicket] = useState(null);
  const [comments, setComments] = useState([]);
  const [history, setHistory] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [agents, setAgents] = useState([]);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    setError("");
    setNotFound(false);
    try {
      const [t, c, a] = await Promise.all([
        api.get(`/api/tickets/${id}`),
        api.get(`/api/tickets/${id}/comments`),
        api.get(`/api/tickets/${id}/attachments`),
      ]);
      setTicket(t.data);
      setComments(c.data);
      setAttachments(a.data);
      if (isStaff) {
        const h = await api.get(`/api/tickets/${id}/history`);
        setHistory(h.data);
      }
    } catch (err) {
      if (err.response?.status === 404) setNotFound(true);
      else setError(apiErrorMessage(err, "Could not load this ticket."));
    }
  }, [id, isStaff]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (isStaff) api.get("/api/users/agents").then((res) => setAgents(res.data));
  }, [isStaff]);

  if (notFound) {
    return (
      <EmptyState
        title="Ticket not found"
        hint="It may not exist, or you may not have permission to view it."
      />
    );
  }
  if (!ticket) return <Loading />;

  const canWorkOn = isStaff && (user.role === "Administrator" || ticket.assigned_to_id === user.id);
  const transitions = isStaff ? STAFF_TRANSITIONS : EMPLOYEE_TRANSITIONS;
  const nextStatuses = canWorkOn || !isStaff ? (transitions[ticket.status] || []) : [];
  const isClosed = ticket.status === "Closed";

  return (
    <div>
      <button className="btn btn-ghost btn-sm" style={{ marginBottom: 16 }} onClick={() => navigate("/tickets")}>
        <IconArrowLeft width={14} height={14} /> Back to tickets
      </button>

      {error && <div className="form-error">{error}</div>}

      <div className="detail-grid">
        <div>
          <div className="panel">
            <div className="panel-body">
              <span className="ticket-id" style={{ color: "var(--muted)", fontSize: 12.5 }}>#{ticket.id}</span>
              <h1 style={{ marginTop: 4 }}>{ticket.title}</h1>
              <div className="detail-meta-row">
                <StatusChip status={ticket.status} />
                <PriorityChip priority={ticket.priority} />
                <span style={{ fontSize: 12.5, color: "var(--muted)" }}>{ticket.category}</span>
                <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                  Reported by {ticket.created_by_name} · {formatDateTime(ticket.created_at)}
                </span>
              </div>
              <p className="detail-desc">{ticket.description}</p>
            </div>
          </div>

          <ActionsPanel
            ticket={ticket} user={user} isStaff={isStaff}
            nextStatuses={nextStatuses} agents={agents} onChanged={load}
          />

          <CommentsPanel ticketId={id} comments={comments} isStaff={isStaff} isClosed={isClosed} onChanged={load} />

          <AttachmentsPanel ticketId={id} attachments={attachments} isClosed={isClosed} onChanged={load} />
        </div>

        <div>
          <div className="panel">
            <div className="panel-body">
              <div className="side-block">
                <h3>Details</h3>
                <div className="kv-row"><span>Status</span><span>{ticket.status}</span></div>
                <div className="kv-row"><span>Priority</span><span>{ticket.priority}</span></div>
                <div className="kv-row"><span>Category</span><span>{ticket.category}</span></div>
                <div className="kv-row"><span>Assigned to</span><span>{ticket.assigned_to_name || "Unassigned"}</span></div>
                <div className="kv-row"><span>Created</span><span>{formatDateTime(ticket.created_at)}</span></div>
                <div className="kv-row"><span>Updated</span><span>{formatDateTime(ticket.updated_at)}</span></div>
                {ticket.resolved_at && <div className="kv-row"><span>Resolved</span><span>{formatDateTime(ticket.resolved_at)}</span></div>}
              </div>
            </div>
          </div>

          {isStaff && history.length > 0 && (
            <div className="panel" style={{ marginTop: 14 }}>
              <div className="panel-header"><h2>History</h2></div>
              <div className="panel-body" style={{ paddingTop: 4 }}>
                {history.map((h) => (
                  <div key={h.id} className="history-item">
                    <span className="history-time">{formatDateTime(h.changed_at)}</span>
                    <span>
                      <strong>{h.changed_by_name}</strong>{" "}
                      {h.field === "created" ? "created the ticket" : `changed ${h.field}${h.new_value ? ` to ${h.new_value}` : ""}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionsPanel({ ticket, user, isStaff, nextStatuses, agents, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [assignTo, setAssignTo] = useState("");

  async function changeStatus(status) {
    setBusy(true); setError("");
    try {
      await api.put(`/api/tickets/${ticket.id}`, { status });
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not update the status."));
    } finally {
      setBusy(false);
    }
  }

  async function assign(agentId) {
    setBusy(true); setError("");
    try {
      await api.post(`/api/tickets/${ticket.id}/assign`, agentId ? { agent_id: agentId } : {});
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not assign the ticket."));
    } finally {
      setBusy(false);
    }
  }

  const canAssignSelf = isStaff && (ticket.status === "Open" || ticket.status === "Assigned") &&
    user.role === "IT Support Agent" && ticket.assigned_to_id !== user.id;
  const canAdminAssign = user.role === "Administrator" && ticket.status !== "Resolved" && ticket.status !== "Closed";

  if (!isStaff && nextStatuses.length === 0 && ticket.status !== "Open") return null;
  if (isStaff && !canAssignSelf && !canAdminAssign && nextStatuses.length === 0) return null;

  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <div className="panel-header"><h2>Actions</h2></div>
      <div className="panel-body" style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {error && <div className="form-error" style={{ width: "100%" }}>{error}</div>}

        {canAssignSelf && (
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => assign(null)}>
            Assign to me
          </button>
        )}

        {canAdminAssign && (
          <>
            <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)} style={{ fontSize: 13 }}>
              <option value="">Assign to…</option>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
            </select>
            <button className="btn btn-ghost btn-sm" disabled={busy || !assignTo} onClick={() => assign(Number(assignTo))}>
              Assign
            </button>
          </>
        )}

        {nextStatuses.map((s) => (
          <button key={s} className="btn btn-ghost btn-sm" disabled={busy} onClick={() => changeStatus(s)}>
            {isStaff ? `Move to ${s}` : s === "Closed" ? "Confirm resolved" : "Reopen ticket"}
          </button>
        ))}
      </div>
    </div>
  );
}

function CommentsPanel({ ticketId, comments, isStaff, isClosed, onChanged }) {
  const [body, setBody] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true); setError("");
    try {
      await api.post(`/api/tickets/${ticketId}/comments`, { body, is_internal: isInternal });
      setBody(""); setIsInternal(false);
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not post the comment."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <div className="panel-header"><h2>Comments</h2></div>
      <div className="panel-body">
        {comments.length === 0 && <p style={{ color: "var(--muted)", fontSize: 13 }}>No comments yet.</p>}
        {comments.map((c) => (
          <div key={c.id} className={`comment${c.is_internal ? " internal" : ""}`}>
            <div className="comment-head">
              <span className="comment-author">{c.author_name}</span>
              <span style={{ color: "var(--muted)" }}>({c.author_role})</span>
              <span className="comment-time">{formatDateTime(c.created_at)}</span>
              {c.is_internal && <span className="comment-internal-tag">Internal note</span>}
            </div>
            <div className="comment-body">{c.body}</div>
          </div>
        ))}

        {!isClosed && (
          <form onSubmit={submit} style={{ marginTop: 14 }}>
            {error && <div className="form-error">{error}</div>}
            <div className="field">
              <textarea
                placeholder="Add a comment…" value={body} maxLength={5000}
                onChange={(e) => setBody(e.target.value)}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              {isStaff ? (
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                  <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} />
                  Internal note (staff only)
                </label>
              ) : <span />}
              <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>
                {busy ? "Posting…" : "Post comment"}
              </button>
            </div>
          </form>
        )}
        {isClosed && <p className="field-hint" style={{ marginTop: 10 }}>This ticket is closed and cannot receive new comments.</p>}
      </div>
    </div>
  );
}

function AttachmentsPanel({ ticketId, attachments, isClosed, onChanged }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true); setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post(`/api/tickets/${ticketId}/attachments`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not upload the file."));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function download(att) {
    const res = await api.get(`/api/tickets/${ticketId}/attachments/${att.id}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url; a.download = att.original_filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <div className="panel-header"><h2>Attachments</h2></div>
      <div className="panel-body">
        {error && <div className="form-error">{error}</div>}
        {attachments.length === 0 && <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 10 }}>No files attached.</p>}
        {attachments.map((a) => (
          <div key={a.id} className="attachment-item">
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              <IconPaperclip width={14} height={14} style={{ color: "var(--muted)", flexShrink: 0 }} />
              <span className="attachment-name">{a.original_filename}</span>
              <span className="attachment-meta">{Math.round(a.size_bytes / 1024)} KB</span>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => download(a)}>Download</button>
          </div>
        ))}
        {!isClosed && (
          <div style={{ marginTop: 10 }}>
            <input ref={fileRef} type="file" onChange={handleFile} disabled={busy} accept=".png,.jpg,.jpeg,.pdf,.txt,.log" />
            <div className="field-hint">PNG, JPG, PDF, TXT or LOG · up to 5 MB</div>
          </div>
        )}
      </div>
    </div>
  );
}
