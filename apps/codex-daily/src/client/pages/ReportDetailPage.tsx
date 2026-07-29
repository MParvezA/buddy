import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { ReportSnapshot } from "../../shared/report";
import { getReport, retryNarrative } from "../api/report-client";
import { ReportDigest } from "../features/reports/ReportDigest";

export function ReportDetailPage() {
  const { snapshotId = "" } = useParams();
  const [snapshot, setSnapshot] = useState<ReportSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    getReport(snapshotId).then(setSnapshot).catch((reason: unknown) =>
      setError(reason instanceof Error ? reason.message : "Report could not load."),
    );
  }, [snapshotId]);
  return (
    <article className="secondary-page">
      <Link className="back-link" to="/reports">← Back to report history</Link>
      {error && <p className="inline-notice" role="alert">{error}</p>}
      {snapshot && (
        <>
          <header className="page-header compact">
            <div>
              <p className="eyebrow">{snapshot.trigger.replace("_", " ")}</p>
              <h1>{snapshot.localDate} · snapshot {snapshot.sequence}</h1>
              <p>
                Created {new Date(snapshot.createdAt).toLocaleString()} · cutoff{" "}
                {new Date(snapshot.cutoff).toLocaleString()}
              </p>
            </div>
          </header>
          {(snapshot.narrative.status === "failed" ||
            snapshot.narrative.status === "not_requested") && (
            <button
              type="button"
              className="secondary-button"
              disabled={pending}
              onClick={() => {
                setPending(true);
                retryNarrative(snapshot.id)
                  .then(setSnapshot)
                  .catch((reason: unknown) =>
                    setError(reason instanceof Error ? reason.message : "Narrative retry failed."),
                  )
                  .finally(() => setPending(false));
              }}
            >
              {pending ? "Requesting…" : "Request generated narrative"}
            </button>
          )}
          <ReportDigest snapshot={snapshot} />
        </>
      )}
    </article>
  );
}
