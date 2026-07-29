import { Link } from "react-router-dom";
import type { ObservedThread } from "../../../shared/observer-types";
import type {
  SessionBriefAnalysisStatus,
  SessionBriefFailureCategory,
  SessionBriefItem,
} from "../../../shared/session-briefs";
import { StatusBadge } from "../../components/StatusBadge";
import { ThreadLinks } from "./ThreadLinks";

function formatTime(value: string | null, timezone: string) {
  if (!value) return "No activity yet";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

function threadTone(thread: ObservedThread): "working" | "waiting" | "possibly-stale" {
  if (thread.waitingOnApproval || thread.waitingOnUserInput) return "waiting";
  if (thread.runtime === "active") return "working";
  return "possibly-stale";
}

function threadStatus(thread: ObservedThread): string {
  if (thread.waitingOnApproval) return "Waiting on approval";
  if (thread.waitingOnUserInput) return "Waiting on your input";
  if (thread.runtime === "active") return "Working";
  if (thread.runtime === "idle") return "Idle";
  if (thread.runtime === "not_loaded") return "History only";
  if (thread.runtime === "system_error") return "System error";
  return "Unknown";
}

const lifecycleCopy: Record<SessionBriefAnalysisStatus, string> = {
  queued: "Queued",
  analyzing: "Analyzing",
  ready: "Ready",
  unavailable: "Unavailable",
  failed: "Failed",
};

const failureCopy: Record<SessionBriefFailureCategory, string> = {
  observer_unavailable: "Codex connection is unavailable.",
  source_missing: "The source session is no longer available.",
  empty_usable_content: "No usable session text was available for analysis.",
  analysis_unavailable: "GPT-5.6 analysis is unavailable.",
  timeout: "GPT-5.6 analysis timed out.",
  refusal: "GPT-5.6 could not produce a brief.",
  invalid_output: "GPT-5.6 returned an invalid brief.",
  internal: "The brief could not be generated.",
};

function listOrFallback(items: string[], fallback: string) {
  if (items.length === 0) return <p className="brief-empty">{fallback}</p>;
  return (
    <ul>
      {items.map((item, index) => (
        <li key={`${index}:${item}`}>{item}</li>
      ))}
    </ul>
  );
}

interface SessionBriefCardProps {
  item: SessionBriefItem;
  thread: ObservedThread | null;
  timezone: string;
  canAnalyze: boolean;
  retryPending: boolean;
  linked: boolean;
  onRetry: (threadId: string) => void;
}

export function SessionBriefCard({
  item,
  thread,
  timezone,
  canAnalyze,
  retryPending,
  linked,
  onRetry,
}: SessionBriefCardProps) {
  const title = thread?.title ?? "Codex session";
  const showRetry =
    item.analysisStatus === "failed" || item.analysisStatus === "unavailable";
  const lifecycleDetail =
    item.analysisStatus === "queued"
      ? "Queued for GPT-5.6 analysis"
      : item.analysisStatus === "analyzing"
        ? "GPT-5.6 analysis in progress"
        : item.analysisStatus === "unavailable"
          ? "GPT-5.6 refresh is unavailable"
          : item.analysisStatus === "failed"
            ? "GPT-5.6 brief generation failed"
            : "GPT-5.6 brief is ready";

  return (
    <li className="session-brief-card" data-thread-id={item.threadId}>
      <div className="card-meta">
        {thread ? (
          <StatusBadge tone={threadTone(thread)}>{threadStatus(thread)}</StatusBadge>
        ) : (
          <StatusBadge tone="possibly-stale">Metadata refreshing</StatusBadge>
        )}
        <time dateTime={thread?.recencyAt ?? thread?.updatedAt ?? item.targetUpdatedAt}>
          {formatTime(
            thread?.lastActivityAt ??
              thread?.recencyAt ??
              thread?.updatedAt ??
              item.targetUpdatedAt,
            timezone,
          )}
        </time>
      </div>

      <h3>
        <Link to={`/threads/${item.threadId}`}>{title}</Link>
      </h3>
      {thread ? (
        <>
          <p className="thread-metadata">
            <span>{thread.source}</span>
            <span>{thread.cwd}</span>
          </p>
          {!linked && <StatusBadge tone="unplanned">Unplanned work</StatusBadge>}
          <ThreadLinks thread={thread} />
        </>
      ) : (
        <p className="quiet-copy">Factual session metadata is refreshing.</p>
      )}

      <div className="brief-lifecycle">
        <StatusBadge
          tone={
            item.analysisStatus === "failed"
              ? "blocked"
              : item.analysisStatus === "ready"
                ? "generated"
                : "pending"
          }
        >
          {lifecycleCopy[item.analysisStatus]}
        </StatusBadge>
        <span>{lifecycleDetail}</span>
      </div>

      {item.lastGood ? (
        <div
          className={`brief-result ${item.freshness === "stale" ? "is-stale" : ""}`}
        >
          <div className="brief-provenance">
            <span>GPT-5.6 derived</span>
            <span>{`${item.lastGood.confidence[0]!.toUpperCase()}${item.lastGood.confidence.slice(1)} confidence`}</span>
            <span>{item.freshness === "stale" ? "Stale" : "Current"}</span>
            <time dateTime={item.lastGood.generatedAt}>
              Generated {formatTime(item.lastGood.generatedAt, timezone)}
            </time>
          </div>
          {item.lastGood.currentState.trim() ? (
            <div className="brief-block brief-current-state">
              <h4>Going on</h4>
              <p>{item.lastGood.currentState}</p>
            </div>
          ) : (
            <p className="brief-failure">
              The generated brief failed validation; factual metadata remains available.
            </p>
          )}
          <div className="brief-block">
            <h4>Chat-reported done</h4>
            {listOrFallback(item.lastGood.done, "No completed work inferred")}
          </div>
          <div className="brief-block">
            <h4>What you should do</h4>
            {listOrFallback(item.lastGood.operatorActions, "No action inferred")}
          </div>
          <div className="brief-block">
            <h4>Blockers</h4>
            {listOrFallback(item.lastGood.blockers, "No blocker inferred")}
          </div>
          {item.lastGood.evidence.length > 0 && (
            <p className="brief-evidence">
              Evidence labels: {item.lastGood.evidence.join(" · ")}
            </p>
          )}
        </div>
      ) : (
        <p className="brief-placeholder">
          {item.analysisStatus === "queued"
            ? "The factual session is available while its generated brief waits."
            : item.analysisStatus === "analyzing"
              ? "The factual session remains available during analysis."
              : "No generated brief is available; factual session metadata remains available."}
        </p>
      )}

      {item.failure && (
        <p className="brief-failure">{failureCopy[item.failure.category]}</p>
      )}

      {showRetry && (
        <div className="brief-retry">
          <button
            type="button"
            className="secondary-button"
            aria-label={`Retry brief for ${title}`}
            disabled={!canAnalyze}
            aria-disabled={!canAnalyze || retryPending}
            onClick={() => {
              if (!retryPending) onRetry(item.threadId);
            }}
          >
            {retryPending ? "Retrying brief…" : "Retry brief"}
          </button>
          {!canAnalyze && (
            <span>Retry is unavailable while Codex is disconnected.</span>
          )}
        </div>
      )}
    </li>
  );
}
