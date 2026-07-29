import { useState } from "react";
import type { PlanningTask } from "../../../shared/planning";
import { StatusBadge } from "../../components/StatusBadge";

interface TodayOutcomesProps {
  tasks: PlanningTask[];
  pendingId: string | null;
  onAdd: (input: { title: string; clarification: string | null }) => Promise<void>;
  onEdit: (
    id: string,
    input: { title: string; clarification: string | null },
  ) => Promise<void>;
  onReorder: (ids: string[]) => Promise<void>;
  onTransition: (id: string, action: "confirm" | "reopen") => Promise<void>;
}

export function TodayOutcomes(props: TodayOutcomesProps) {
  const [title, setTitle] = useState("");
  const [clarification, setClarification] = useState("");
  const [editing, setEditing] = useState<string | null>(null);

  const submitAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await props.onAdd({ title, clarification: clarification || null });
      setTitle("");
      setClarification("");
    } catch {
      // Keep the authored values for correction.
    }
  };

  const move = (index: number, offset: number) => {
    const next = props.tasks.map((task) => task.id);
    const [id] = next.splice(index, 1);
    next.splice(index + offset, 0, id);
    void props.onReorder(next).catch(() => undefined);
  };

  return (
    <div className="planning-editor">
      <form className="outcome-form" onSubmit={(event) => void submitAdd(event)}>
        <div>
          <label htmlFor="new-outcome">Today’s outcome</label>
          <input
            id="new-outcome"
            value={title}
            maxLength={240}
            required
            disabled={props.pendingId !== null}
            placeholder="What result should be true by this evening?"
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="new-clarification">Clarification (optional)</label>
          <textarea
            id="new-clarification"
            value={clarification}
            maxLength={2000}
            rows={2}
            disabled={props.pendingId !== null}
            placeholder="Success criteria or useful context"
            onChange={(event) => setClarification(event.target.value)}
          />
        </div>
        <button className="primary-button" disabled={props.pendingId !== null} type="submit">
          {props.pendingId === "create" ? "Adding…" : "Add outcome"}
        </button>
      </form>

      {props.tasks.length === 0 ? (
        <p className="planning-empty">No outcomes yet. Start with the result that matters most.</p>
      ) : (
        <ul className="outcome-list">
          {props.tasks.map((task, index) => (
            <li key={task.id} className="outcome-row durable-outcome">
              <div
                className={`outcome-icon ${
                  task.lifecycle === "confirmed_complete" ? "outcome-confirmed" : ""
                }`}
                aria-hidden="true"
              >
                {task.lifecycle === "confirmed_complete" ? "✓" : index + 1}
              </div>
              <div className="outcome-copy">
                {editing === task.id ? (
                  <EditOutcome
                    task={task}
                    pending={props.pendingId === task.id}
                    onCancel={() => setEditing(null)}
                    onSave={async (input) => {
                      await props.onEdit(task.id, input);
                      setEditing(null);
                    }}
                  />
                ) : (
                  <>
                    <h3>{task.title}</h3>
                    {task.clarification && <p>{task.clarification}</p>}
                    <StatusBadge
                      tone={task.lifecycle === "confirmed_complete" ? "confirmed" : "pending"}
                    >
                      {task.lifecycle === "confirmed_complete"
                        ? "Operator confirmed complete"
                        : "Open"}
                    </StatusBadge>
                    <div className="outcome-actions">
                      <button
                        type="button"
                        disabled={props.pendingId !== null}
                        onClick={() => setEditing(task.id)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={index === 0 || props.pendingId !== null}
                        onClick={() => move(index, -1)}
                        aria-label={`Move ${task.title} up`}
                      >
                        Move up
                      </button>
                      <button
                        type="button"
                        disabled={index === props.tasks.length - 1 || props.pendingId !== null}
                        onClick={() => move(index, 1)}
                        aria-label={`Move ${task.title} down`}
                      >
                        Move down
                      </button>
                      <button
                        type="button"
                        disabled={props.pendingId !== null}
                        onClick={() =>
                          void props
                            .onTransition(
                              task.id,
                              task.lifecycle === "confirmed_complete" ? "reopen" : "confirm",
                            )
                            .catch(() => undefined)
                        }
                      >
                        {task.lifecycle === "confirmed_complete"
                          ? "Reopen outcome"
                          : "Confirm complete"}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EditOutcome({
  task,
  pending,
  onCancel,
  onSave,
}: {
  task: PlanningTask;
  pending: boolean;
  onCancel: () => void;
  onSave: (input: { title: string; clarification: string | null }) => Promise<void>;
}) {
  const [title, setTitle] = useState(task.title);
  const [clarification, setClarification] = useState(task.clarification ?? "");
  return (
    <form
      className="edit-outcome-form"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({ title, clarification: clarification || null }).catch(() => undefined);
      }}
    >
      <label htmlFor={`title-${task.id}`}>Outcome</label>
      <input
        id={`title-${task.id}`}
        required
        maxLength={240}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <label htmlFor={`clarification-${task.id}`}>Clarification</label>
      <textarea
        id={`clarification-${task.id}`}
        rows={2}
        maxLength={2000}
        value={clarification}
        onChange={(event) => setClarification(event.target.value)}
      />
      <div className="outcome-actions">
        <button type="submit" disabled={pending}>Save changes</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
