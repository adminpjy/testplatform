export interface StatusBadgeProps {
  value: string | null | undefined;
}

export function StatusBadge({ value }: StatusBadgeProps) {
  const normalized = (value || "unknown").toLowerCase();
  return <span className={`status-badge status-badge--${normalized}`}>{value || "unknown"}</span>;
}
