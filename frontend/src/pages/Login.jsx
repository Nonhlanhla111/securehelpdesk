import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const justRegistered = location.state?.registered;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Could not log in. Check your email and password."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark">SH</span>
          <span>SecureHelpDesk</span>
        </div>
        <p className="auth-sub">Sign in to report or manage IT issues.</p>

        {justRegistered && (
          <div className="form-notice">Account created. You can log in now.</div>
        )}
        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Work email</label>
            <input
              id="email" type="email" required autoFocus autoComplete="username"
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password" type="password" required autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-full" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p style={{ marginTop: 18, fontSize: 13, color: "var(--muted)", textAlign: "center" }}>
          New here? <Link to="/register">Create an employee account</Link>
        </p>
      </div>
    </div>
  );
}
