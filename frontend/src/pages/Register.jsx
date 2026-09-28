import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../api/client";
import { AuthThemeToggle } from "../components/AuthThemeToggle";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(email, fullName, password);
      navigate("/login", { state: { registered: true } });
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <AuthThemeToggle />
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark">SH</span>
          <span>SecureHelpDesk</span>
        </div>
        <p className="auth-sub">New accounts start as Employee. An administrator can change your role later.</p>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input id="fullName" required autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="email">Work email</label>
            <input id="email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <div className="field-hint">At least 10 characters, with upper-case, lower-case and a digit.</div>
          </div>
          <button className="btn btn-primary btn-full" type="submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p style={{ marginTop: 18, fontSize: 13, color: "var(--muted)", textAlign: "center" }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
