import { useState } from "react";
import type { PlanningTask, ReviewDecisionRequest } from "../../../shared/planning";

interface PriorDayReviewProps {
  priorDayLocalDate: string;
  todayLocalDate: string;
  tasks: PlanningTask[];
  pendingId: string | null;
  onDecision: (taskId: string, request: ReviewDecisionRequest) => Promise<void>;
}

export function PriorDayReview({
  priorDayLocalDate,
  todayLocalDate,
  tasks,
  pendingId,
  onDecision,
}: PriorDayReviewProps) {
  const [rescheduling, setRescheduling] = useState<string | null>(null);
  const [dates, setDates] = useState<Record<string, string>>({});
  const firstFutureDate = new Date(`${todayLocalDate}T12:00:00Z`);
  firstFutureDate.setUTCDate(firstFutureDate.getUTCDate() + 1);

  const submit = async (taskId: string, request: ReviewDecisionRequest) => {
    try {
      await onDecision(taskId, request);
      setRescheduling(null);
    } catch {
      // The shared status region explains the service error and the entered date remains intact.
    }
  };

  return (
    <div className="review-gate">
      <div className="review-intro">
        <StatusLine>Morning review required</StatusLine>
        <p>
          Decide what happens to every unfinished outcome from{" "}
          <strong>{priorDayLocalDate}</strong>.
          Nothing moves automatically.
        </p>
      </div>
      <ul className="review-list">
        {tasks.map((task) => {
          const pending = pendingId === task.id;
          return (
            <li key={task.id} className="review-card">
              <p className="historical-date">Unfinished from {task.localDate}</p>
              <h3>{task.title}</h3>
              {task.clarification && <p>{task.clarification}</p>}
              <div className="review-actions" aria-label={`Review ${task.title}`}>
                <button
                  type="button"
                  disabled={pendingId !== null}
                  onClick={() => void submit(task.id, { action: "carry_forward" })}
                >
                  Carry forward
                </button>
                <button
                  type="button"
                  disabled={pendingId !== null}
                  onClick={() => setRescheduling(task.id)}
                >
                  Reschedule
                </button>
                <button
                  type="button"
                  disabled={pendingId !== null}
                  onClick={() => void submit(task.id, { action: "close" })}
                >
                  Close
                </button>
              </div>
              {rescheduling === task.id && (
                <div className="reschedule-form">
                  <label htmlFor={`reschedule-${task.id}`}>New date</label>
                  <input
                    id={`reschedule-${task.id}`}
                    type="date"
                    min={firstFutureDate.toISOString().slice(0, 10)}
                    required
                    value={dates[task.id] ?? ""}
                    onChange={(event) =>
                      setDates((current) => ({ ...current, [task.id]: event.target.value }))
                    }
                  />
                  <button
                    type="button"
                    disabled={
                      !dates[task.id] ||
                      dates[task.id] <= todayLocalDate ||
                      pendingId !== null
                    }
                    onClick={() =>
                      void submit(task.id, {
                        action: "reschedule",
                        rescheduleDate: dates[task.id],
                      })
                    }
                  >
                    Save new date
                  </button>
                </div>
              )}
              {pending && <small className="pending-copy">Saving decision…</small>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function StatusLine({ children }: { children: React.ReactNode }) {
  return <span className="status-badge status-pending">{children}</span>;
}
