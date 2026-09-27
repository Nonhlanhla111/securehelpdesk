export function StatusChip({ status }) {
  const key = status.replace(/\s+/g, "");
  return <span className={`chip chip-status-${key}`}>{status}</span>;
}

export function PriorityChip({ priority }) {
  return <span className={`chip chip-priority-${priority}`}>{priority}</span>;
}

export function PriorityBar({ priority }) {
  return <div className={`priority-bar ${priority}`} />;
}

export function SeverityDot({ severity }) {
  return <span className={`severity-dot severity-${severity}`} />;
}
