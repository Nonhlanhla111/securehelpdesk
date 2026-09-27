import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";

const CATEGORIES = ["Hardware", "Software", "Network", "Account Access", "Security", "Email", "System Issues", "Other"];
const PRIORITIES = ["Low", "Medium", "High", "Critical"];

export default function NewTicket() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("Hardware");
  const [priority, setPriority] = useState("Medium");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/api/tickets", { title, description, category, priority });
      navigate(`/tickets/${data.id}`);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create the ticket."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      <div className="page-header">
        <div>
          <h1>Report an IT issue</h1>
          <p>Describe the problem clearly so support can help quickly.</p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-body">
          {error && <div className="form-error">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="title">Title</label>
              <input
                id="title" required minLength={5} maxLength={200}
                placeholder="e.g. Unable to connect to company Wi-Fi"
                value={title} onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="description">Description</label>
              <textarea
                id="description" required minLength={10} maxLength={5000}
                placeholder="What happened, when it started, and anything you've already tried."
                value={description} onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="field-row">
              <div className="field">
                <label htmlFor="category">Category</label>
                <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="priority">Priority</label>
                <select id="priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? "Submitting…" : "Submit ticket"}
              </button>
              <button className="btn btn-ghost" type="button" onClick={() => navigate(-1)}>Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
