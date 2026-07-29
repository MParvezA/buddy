import { Link } from "react-router-dom";
import { useObserver } from "../../data/observer-context";
import { usePlanning } from "../../data/planning-context";

function formatTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: timezone,
  }).format(new Date(value));
}

export function RecentlyCompletedWork() {
  const observer = useObserver();
  const planning = usePlanning();
  const timezone = planning.view?.timezone ?? "Europe/Berlin";
  const recent = (observer.snapshot?.activities ?? [])
    .filter((item) => item.category === "turn" && item.lifecycle === "completed")
    .slice(0, 8);

  return (
    <section className="panel" data-section-order="4" aria-labelledby="completed-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Priority 04</p>
          <h2 id="completed-title">Recently completed work</h2>
        </div>
        <span className="section-hint">Observed turn facts, not task confirmation</span>
      </div>
      {recent.length === 0 ? (
        <div className="empty-inline">
          <p>No completed Codex turns have been observed.</p>
        </div>
      ) : (
        <ul className="completed-list">
          {recent.map((item) => {
            const thread = observer.snapshot?.threads.find(
              (candidate) => candidate.id === item.threadId,
            );
            return (
              <li key={item.sourceKey}>
                <span className="completion-mark" aria-hidden="true">✓</span>
                <div>
                  <h3>
                    <Link to={`/threads/${item.threadId}`}>
                      {thread?.title ?? "Untitled Codex chat"}
                    </Link>
                  </h3>
                  <p>{item.label}</p>
                </div>
                <time dateTime={item.occurredAt}>
                  {formatTime(item.occurredAt, timezone)}
                </time>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
