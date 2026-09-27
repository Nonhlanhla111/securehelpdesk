export function Loading({ label = "Loading…" }) {
  return <div className="spinner-wrap">{label}</div>;
}

export function EmptyState({ title, hint }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      {hint && <p>{hint}</p>}
    </div>
  );
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z"); // backend sends naive UTC
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase();
}
