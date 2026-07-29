import { Link } from "react-router-dom";
import { usePlanning } from "../../data/planning-context";
import { useReports } from "../../data/report-context";
import { ReportDigest } from "./ReportDigest";

export function ReportPreview() {
  const reports = useReports();
  const planning = usePlanning();
  return (
    <section className="panel report-panel" data-section-order="5" aria-labelledby="report-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Priority 05</p>
          <h2 id="report-title">Evening report</h2>
        </div>
        <Link className="text-link" to="/reports">Open report history →</Link>
      </div>
      <p className="section-hint">
        Next run {reports.scheduler ? new Date(reports.scheduler.nextRunAt).toLocaleString() : "loading"}.
      </p>
      {reports.error && <p className="inline-notice" role="alert">{reports.error}</p>}
      <button
        className="secondary-button"
        type="button"
        disabled={reports.pending || !planning.view}
        onClick={() => {
          void reports.generate(planning.view?.localDate).catch(() => undefined);
        }}
      >
        {reports.pending ? "Generating…" : "Generate report"}
      </button>
      {reports.latest ? (
        <ReportDigest snapshot={reports.latest} />
      ) : (
        <div className="empty-inline">
          <h3>No factual snapshot yet</h3>
          <p>Generate one now or leave Codex Daily open for the automatic run.</p>
        </div>
      )}
    </section>
  );
}
