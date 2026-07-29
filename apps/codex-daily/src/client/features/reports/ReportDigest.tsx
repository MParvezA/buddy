import type { FactualDigest, ReportSnapshot } from "../../../shared/report";
import { StatusBadge } from "../../components/StatusBadge";

const sections: Array<{
  key: keyof Pick<
    FactualDigest,
    "confirmedComplete" | "suggestedComplete" | "pending" | "blocked"
  >;
  title: string;
}> = [
  { key: "confirmedComplete", title: "Confirmed complete" },
  { key: "suggestedComplete", title: "Suggested complete" },
  { key: "pending", title: "Pending" },
  { key: "blocked", title: "Blocked" },
];

export function ReportDigest({ snapshot }: { snapshot: ReportSnapshot }) {
  const digest = snapshot.factualDigest;
  return (
    <div className="report-detail-stack">
      <section className="fact-block" aria-labelledby={`facts-${snapshot.id}`}>
        <div className="block-label">
          <StatusBadge tone="fact">Recorded facts</StatusBadge>
          <span id={`facts-${snapshot.id}`}>Frozen at {new Date(snapshot.cutoff).toLocaleString()}</span>
        </div>
        <div className="report-fact-sections">
          {sections.map(({ key, title }) => (
            <div key={key}>
              <h3>{title}</h3>
              {digest[key].length ? (
                <ul>{digest[key].map((task) => <li key={task.taskId}>{task.title}</li>)}</ul>
              ) : (
                <p className="muted-copy">None</p>
              )}
            </div>
          ))}
          <div>
            <h3>Unplanned observed work</h3>
            {digest.unplannedWork.length ? (
              <ul>{digest.unplannedWork.map((item) => <li key={item.threadId}>{item.title}</li>)}</ul>
            ) : (
              <p className="muted-copy">None</p>
            )}
          </div>
          <div>
            <h3>Outstanding attention</h3>
            {digest.outstandingAttention.length ? (
              <ul>
                {digest.outstandingAttention.map((item) => (
                  <li key={item.attentionId}>{item.label} · {item.certainty}</li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">None</p>
            )}
          </div>
          <div>
            <h3>Consider tomorrow</h3>
            {digest.considerTomorrow.length ? (
              <ul>
                {digest.considerTomorrow.map((item) => (
                  <li key={`${item.kind}:${item.id}`}>{item.label} · {item.reason}</li>
                ))}
              </ul>
            ) : (
              <p className="muted-copy">Nothing suggested</p>
            )}
          </div>
        </div>
      </section>
      <aside className="interpretation-block" aria-label="Generated interpretation">
        <StatusBadge tone="generated">Generated interpretation</StatusBadge>
        {snapshot.narrative.status === "ready" ? (
          <>
            <p>{snapshot.narrative.text}</p>
            {snapshot.narrative.suggestions.map((item) => (
              <div className="generated-suggestion" key={item.id}>
                <strong>
                  {digest.planned.find((task) => task.taskId === item.taskId)?.title ??
                    "Unknown task"}{" "}
                  · completion suggestion
                </strong>
                <p>{item.reason}</p>
                <small>Generated only · confirm completion from Today.</small>
              </div>
            ))}
          </>
        ) : snapshot.narrative.status === "failed" ? (
          <p role="alert">Narrative unavailable. Your recorded facts are complete.</p>
        ) : snapshot.narrative.status === "pending" ? (
          <p role="status">Generating optional interpretation…</p>
        ) : (
          <p>Optional interpretation was not requested.</p>
        )}
      </aside>
    </div>
  );
}
