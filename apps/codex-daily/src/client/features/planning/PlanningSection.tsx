import { usePlanning } from "../../data/planning-context";
import { PriorDayReview } from "./PriorDayReview";
import { TodayOutcomes } from "./TodayOutcomes";

export function PlanningSection() {
  const planning = usePlanning();
  const confirmed =
    planning.view?.tasks.filter((task) => task.lifecycle === "confirmed_complete").length ?? 0;
  const total = planning.view?.tasks.length ?? 0;

  return (
    <section className="panel" data-section-order="2" aria-labelledby="outcomes-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Priority 02</p>
          <h2 id="outcomes-title">Today’s outcomes and progress</h2>
        </div>
        <span className="progress-copy">
          <strong>{confirmed}</strong> / {total} confirmed
        </span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label="Confirmed outcomes"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={confirmed}
      >
        <span style={{ width: total ? `${(confirmed / total) * 100}%` : "0%" }} />
      </div>

      {planning.error && (
        <div className="planning-status error-message" role="alert">
          <span>{planning.error}</span>
          {!planning.view && (
            <button type="button" onClick={planning.reload}>
              Try again
            </button>
          )}
        </div>
      )}
      {planning.loading && !planning.view && (
        <p className="planning-status" role="status">Loading local planning…</p>
      )}
      {planning.view?.reviewRequired && (
        <PriorDayReview
          priorDayLocalDate={planning.view.priorDay.localDate}
          todayLocalDate={planning.view.localDate}
          tasks={planning.view.priorDay.unresolvedTasks}
          pendingId={planning.pendingId}
          onDecision={planning.review}
        />
      )}
      {planning.view && !planning.view.reviewRequired && (
        <TodayOutcomes
          tasks={planning.view.tasks}
          pendingId={planning.pendingId}
          onAdd={planning.add}
          onEdit={planning.edit}
          onReorder={planning.reorder}
          onTransition={planning.transition}
        />
      )}
    </section>
  );
}
