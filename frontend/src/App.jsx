import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { AppLayout, RequireRole } from "./components/Layout";
import { Loading } from "./components/Loading";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import TicketList from "./pages/TicketList";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";
import Reports from "./pages/Reports";
import AdminUsers from "./pages/AdminUsers";
import AdminLogs from "./pages/AdminLogs";

const STAFF = ["IT Support Agent", "Administrator"];
const ADMIN = ["Administrator"];

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />

        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tickets" element={<TicketList />} />
          <Route path="/tickets/new" element={<NewTicket />} />
          <Route path="/tickets/:id" element={<TicketDetail />} />
          <Route path="/reports" element={<RequireRole roles={STAFF}><Reports /></RequireRole>} />
          <Route path="/admin/users" element={<RequireRole roles={ADMIN}><AdminUsers /></RequireRole>} />
          <Route path="/admin/logs" element={<RequireRole roles={ADMIN}><AdminLogs /></RequireRole>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
