import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading, EmptyState, formatDateTime } from "../components/Loading";

const ROLES = ["Employee", "IT Support Agent", "Administrator"];

export default function AdminUsers() {
  const { user: me } = useAuth();
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    const params = {};
    if (q.trim()) params.q = q.trim();
    if (role) params.role = role;
    api.get("/api/users", { params }).then((res) => {
      setItems(res.data.items);
      setTotal(res.data.total);
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, role]);

  async function updateUser(id, patch) {
    setError("");
    try {
      await api.put(`/api/users/${id}`, patch);
      load();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not update that user."));
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Users</h1>
          <p>{total} account{total === 1 ? "" : "s"}. Manage roles and access here.</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>Add user</button>
      </div>

      {error && <div className="form-error">{error}</div>}

      <div className="filters-bar">
        <input placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: "1 1 220px" }} />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Any role</option>
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      <div className="panel">
        {!items && <Loading />}
        {items && items.length === 0 && <EmptyState title="No users match" />}
        {items && items.length > 0 && (
          <table className="data-table">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th></th></tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <select
                      value={u.role} disabled={u.id === me.id}
                      onChange={(e) => updateUser(u.id, { role: e.target.value })}
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>{u.is_active ? "Active" : "Deactivated"}</td>
                  <td>{u.last_login_at ? formatDateTime(u.last_login_at) : "Never"}</td>
                  <td>
                    {u.id !== me.id && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} onCreated={load} />}
    </div>
  );
}

function CreateUserModal({ onClose, onCreated }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("Employee");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api.post("/api/users", { email, full_name: fullName, password, role });
      onCreated();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create the user."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginBottom: 14 }}>Add a user</h2>
        {error && <div className="form-error">{error}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label>Full name</label>
            <input required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label>Temporary password</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            <div className="field-hint">At least 10 characters, with upper-case, lower-case and a digit.</div>
          </div>
          <div className="field">
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Creating…" : "Create user"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
