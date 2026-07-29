import { useState } from "react";
import type { ObservedThread } from "../../../shared/observer-types";
import { useObserver } from "../../data/observer-context";
import { usePlanning } from "../../data/planning-context";

export function ThreadLinks({ thread }: { thread: ObservedThread }) {
  const planning = usePlanning();
  const observer = useObserver();
  const [selected, setSelected] = useState("");
  const links =
    observer.snapshot?.taskLinks.filter((link) => link.threadId === thread.id) ?? [];
  const available =
    planning.view?.tasks.filter(
      (task) => !links.some((link) => link.taskId === task.id),
    ) ?? [];

  return (
    <div className="thread-links">
      {links.map((link) => {
        const task = planning.view?.tasks.find((item) => item.id === link.taskId);
        return (
          <span className="thread-link-chip" key={link.taskId}>
            {task?.title ?? "Linked outcome"}
            <button
              type="button"
              aria-label={`Unlink ${task?.title ?? "outcome"} from ${thread.title ?? "Codex chat"}`}
              disabled={observer.pendingLink === `${link.taskId}:${thread.id}`}
              onClick={() => void observer.unlinkTask(link.taskId, thread.id)}
            >
              ×
            </button>
          </span>
        );
      })}
      {available.length > 0 && (
        <form
          className="thread-link-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!selected) return;
            void observer.linkTask(selected, thread.id).then(() => setSelected(""));
          }}
        >
          <label>
            <span className="visually-hidden">
              Link an outcome to {thread.title ?? "Codex chat"}
            </span>
            <select
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Link outcome…</option>
              {available.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="text-button" disabled={!selected}>
            Link
          </button>
        </form>
      )}
      {links.length === 0 && available.length === 0 && (
        <small>No outcomes available to link.</small>
      )}
    </div>
  );
}
