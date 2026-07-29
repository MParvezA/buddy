import type { AttentionKind } from "../../shared/attention";
import type { ThreadStatus } from "../../shared/dashboard";

type StatusTone =
  | AttentionKind
  | ThreadStatus
  | "pending"
  | "confirmed"
  | "unplanned"
  | "fact"
  | "generated";

interface StatusBadgeProps {
  tone: StatusTone;
  children: React.ReactNode;
}

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
}
