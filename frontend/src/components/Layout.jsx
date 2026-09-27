import { Navigate, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Sidebar } from "./Sidebar";
import { IconPlus } from "./Icons";
import { Loading } from "./Loading";

export function AppLayout() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  if (loading) return <Loading label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <div className="topbar">
          <div style={{ fontWeight: 600, color: "var(--ink-soft)", fontSize: 13 }}>
            {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => navigate("/tickets/new")}>
            <IconPlus width={14} height={14} /> New ticket
          </button>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export function RequireRole({ roles, children }) {
  const { user } = useAuth();
  if (!roles.includes(user.role)) {
    return (
      <div className="empty-state">
        <h3>You don't have access to this page</h3>
        <p>This area is restricted to: {roles.join(", ")}.</p>
      </div>
    );
  }
  return children;
}
