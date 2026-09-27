import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { IconDashboard, IconTicket, IconUsers, IconShield, IconChart } from "./Icons";
import { initials } from "./Loading";

export function Sidebar() {
  const { user, logout } = useAuth();
  const isStaff = user.role === "IT Support Agent" || user.role === "Administrator";
  const isAdmin = user.role === "Administrator";

  const link = (to, Icon, label) => (
    <NavLink to={to} end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
      <Icon /> {label}
    </NavLink>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">SH</span>
        SecureHelpDesk
      </div>

      <nav>
        {link("/", IconDashboard, "Dashboard")}
        {link("/tickets", IconTicket, "Tickets")}

        {isStaff && (
          <div className="nav-section">
            <div className="nav-label">Staff</div>
            {link("/reports", IconChart, "Reports")}
          </div>
        )}

        {isAdmin && (
          <div className="nav-section">
            <div className="nav-label">Administration</div>
            {link("/admin/users", IconUsers, "Users")}
            {link("/admin/logs", IconShield, "Audit & Security")}
          </div>
        )}
      </nav>

      <div className="sidebar-foot">
        <div className="user-chip">
          <div className="user-avatar">{initials(user.full_name)}</div>
          <div className="user-meta">
            <div className="user-name">{user.full_name}</div>
            <div className="user-role">{user.role}</div>
          </div>
        </div>
        <button className="logout-btn" onClick={logout}>Log out</button>
      </div>
    </aside>
  );
}
