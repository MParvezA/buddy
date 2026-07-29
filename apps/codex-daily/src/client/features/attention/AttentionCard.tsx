import { Link } from "react-router-dom";
import type { AttentionItem } from "../../../shared/attention";
import type { ObservedThread } from "../../../shared/observer-types";
import { StatusBadge } from "../../components/StatusBadge";

interface AttentionCardProps {
  item: AttentionItem;
  thread: ObservedThread | null;
  timezone: string;
  pending: boolean;
  onAcknowledge: () => void;
  onDismiss: () => void;
}

const details: Record<AttentionItem["kind"], string> = {
  approval: "Codex is waiting for an approval in the shared live session.",
  direct_question: "Codex is waiting for operator input in the shared live session.",
  failed_turn: "An observed Codex turn ended with a failed status.",
  interrupted_turn: "An observed Codex turn ended before completion.",
  explicit_blocker: "Codex reported a structured blocked goal state.",
  possibly_stale:
    "This chat still appears active, but no new activity has been observed for 30 minutes.",
};

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

export function AttentionCard({
  item,
  thread,
  timezone,
  pending,
  onAcknowledge,
  onDismiss,
}: AttentionCardProps) {
  return (
    <li className={`attention-card certainty-${item.certainty}`}>
      <div className="card-meta">
        <StatusBadge tone={item.kind}>{item.sourceLabel}</StatusBadge>
        <time dateTime={item.sourceOccurredAt}>
          {formatTime(item.sourceOccurredAt, timezone)}
        </time>
      </div>
      <h3>
        <Link to={`/threads/${item.threadId}`}>
          {thread?.title ?? "Untitled Codex chat"}
        </Link>
      </h3>
      <p>{details[item.kind]}</p>
      <div className="attention-source">
        <span>
          {item.certainty === "possible" ? "Possible signal" : "Explicit signal"}
        </span>
        <Link to={`/threads/${item.threadId}`}>View source activity</Link>
      </div>
      <div className="attention-actions" aria-label="Local attention actions">
        <button
          type="button"
          className="secondary-button compact-button"
          disabled={pending}
          onClick={onAcknowledge}
        >
          {pending ? "Saving…" : "Acknowledge"}
        </button>
        <button
          type="button"
          className="text-button compact-button"
          disabled={pending}
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </li>
  );
}
