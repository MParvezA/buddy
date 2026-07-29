import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import type { ReportSchedule, ReportSchedulerState } from "../../shared/report";
import {
  DELETE_ALL_CONFIRMATION,
  type OperationsDiagnostics,
} from "../../shared/operations";
import {
  getReportSettings,
  saveReportSettings,
} from "../api/report-client";
import {
  deleteAllLocalData,
  deleteLocalDay,
  getOperationsDiagnostics,
} from "../api/operations-client";
import { REPORT_SCHEDULE_CHANGED_EVENT } from "../data/invalidation";

export function SettingsPage() {
  const [form, setForm] = useState<ReportSchedule | null>(null);
  const [state, setState] = useState<ReportSchedulerState | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<OperationsDiagnostics | null>(null);
  const [operationsError, setOperationsError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"day" | "all" | null>(null);
  const [deleteDate, setDeleteDate] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const deleteDayButton = useRef<HTMLButtonElement>(null);
  const deleteAllButton = useRef<HTMLButtonElement>(null);
  const confirmationInput = useRef<HTMLInputElement>(null);
  const dialogElement = useRef<HTMLDivElement>(null);
  const loadSettings = useCallback(() => {
    setSettingsLoading(true);
    setError(null);
    getReportSettings()
      .then((result) => {
        setState(result);
        setForm(result.schedule);
      })
      .catch((reason: unknown) => {
        setState(null);
        setForm(null);
        setError(reason instanceof Error ? reason.message : "Settings could not load.");
      })
      .finally(() => setSettingsLoading(false));
  }, []);
  useEffect(() => {
    let active = true;
    getReportSettings()
      .then((result) => {
        if (!active) return;
        setState(result);
        setForm(result.schedule);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setState(null);
        setForm(null);
        setError(reason instanceof Error ? reason.message : "Settings could not load.");
      })
      .finally(() => {
        if (active) setSettingsLoading(false);
      });
    getOperationsDiagnostics()
      .then((result) => {
        setDiagnostics(result);
        setDeleteDate(result.retainedDates.newest ?? "");
      })
      .catch((reason: unknown) =>
        setOperationsError(
          reason instanceof Error ? reason.message : "Diagnostics could not load.",
        ),
      );
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (dialog) confirmationInput.current?.focus();
  }, [dialog]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setStatus(null);
    setError(null);
    try {
      const result = await saveReportSettings(form);
      setState(result);
      setForm(result.schedule);
      setStatus("Report schedule saved.");
      window.dispatchEvent(new Event(REPORT_SCHEDULE_CHANGED_EVENT));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
    }
  }
  function openDialog(kind: "day" | "all") {
    setConfirmation("");
    setOperationsError(null);
    setDeletionError(null);
    setDialog(kind);
  }
  function closeDialog() {
    const opener = dialog === "day" ? deleteDayButton : deleteAllButton;
    setDialog(null);
    setConfirmation("");
    setDeletionError(null);
    window.setTimeout(() => opener.current?.focus(), 0);
  }
  async function confirmDeletion(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;
    setDeleting(true);
    setDeletionError(null);
    try {
      if (dialog === "day") {
        await deleteLocalDay(deleteDate, confirmation);
      } else {
        await deleteAllLocalData(confirmation);
      }
      window.location.reload();
    } catch (reason) {
      setDeletionError(
        reason instanceof Error ? reason.message : "Local data could not be deleted.",
      );
      setDeleting(false);
    }
  }
  function handleDialogKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") return;
    const controls = Array.from(
      dialogElement.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), a[href]",
      ) ?? [],
    );
    if (!controls.length) return;
    const first = controls[0];
    const last = controls.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  const expectedConfirmation =
    dialog === "day" ? `DELETE ${deleteDate}` : DELETE_ALL_CONFIRMATION;
  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Local preferences</p>
          <h1>Settings</h1>
          <p>Schedule the factual report in your local timezone.</p>
        </div>
      </header>
      <form className="panel report-settings" onSubmit={(event) => void submit(event)}>
        <fieldset disabled={settingsLoading || !form}>
          <label>
            Evening report time
            <input
              type="time"
              required
              value={form?.time ?? ""}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, time: event.target.value } : current,
                )
              }
            />
          </label>
          <label>
            IANA timezone
            <input
              required
              value={form?.timezone ?? ""}
              onChange={(event) =>
                setForm((current) =>
                  current ? { ...current, timezone: event.target.value } : current,
                )
              }
              placeholder="Loading retained timezone…"
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={form?.narrativeEnabled ?? false}
              onChange={(event) =>
                setForm((current) =>
                  current
                    ? { ...current, narrativeEnabled: event.target.checked }
                    : current,
                )
              }
            />
            Add optional Codex-generated interpretation
          </label>
          <button className="secondary-button" type="submit">
            Save report settings
          </button>
        </fieldset>
        {settingsLoading && <p role="status">Loading retained report settings…</p>}
        {status && <p role="status">{status}</p>}
        {error && (
          <div className="inline-notice" role="alert">
            <p>{error} Editing remains disabled until retained settings load.</p>
            <button className="text-button" type="button" onClick={loadSettings}>
              Retry settings load
            </button>
          </div>
        )}
        {state?.lastFailure && (
          <p className="inline-notice" role="alert">
            {state.lastFailure} You can generate a factual report manually from Today.
          </p>
        )}
        {state && (
          <small>Next automatic run: {new Date(state.nextRunAt).toLocaleString()}</small>
        )}
      </form>
      <div className="settings-grid">
        <section className="panel setting-card">
          <p className="eyebrow">Retention</p>
          <h2>Metadata and snapshots</h2>
          <p>No full transcripts or browser storage.</p>
          <span className="read-only-label">Minimal local retention</span>
        </section>
        <section className="panel setting-card">
          <p className="eyebrow">Authority</p>
          <h2>Operator confirmed</h2>
          <p>Generated suggestions never complete tasks.</p>
          <span className="read-only-label">Read-only ordinary chats</span>
        </section>
      </div>
      <section className="panel operations-panel" aria-labelledby="local-data-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Local-only operations</p>
            <h2 id="local-data-title">Inspect and manage retained data</h2>
          </div>
          <a className="secondary-button button-link" href="/api/operations/export" download>
            Export JSON
          </a>
        </div>
        <p>
          This export contains Codex Daily plans and normalized metadata only—never
          transcript bodies, credentials, or raw App Server payloads.
        </p>
        {operationsError && <p className="inline-notice" role="alert">{operationsError}</p>}
        {!diagnostics && !operationsError && <p role="status">Loading local diagnostics…</p>}
        {diagnostics && (
          <>
            <dl className="diagnostics-grid">
              <Diagnostic label="Data location" value={diagnostics.dataLocation} />
              <Diagnostic
                label="Database"
                value={`${diagnostics.database.status}; schema ${
                  diagnostics.database.schemaVersion ?? "unknown"
                }; ${diagnostics.database.foreignKeyViolations} foreign-key violations`}
              />
              <Diagnostic
                label="Retained dates"
                value={
                  diagnostics.retainedDates.oldest
                    ? `${diagnostics.retainedDates.oldest} – ${diagnostics.retainedDates.newest}`
                    : "No retained dates"
                }
              />
              <Diagnostic
                label="Observer"
                value={`${diagnostics.observer.state}; last sync ${formatTime(
                  diagnostics.observer.lastSuccessfulSyncAt,
                )}`}
              />
              <Diagnostic
                label="Reconnect"
                value={`attempt ${diagnostics.observer.reconnectAttempt}; backoff ${
                  diagnostics.observer.reconnectBackoffMs ?? 0
                } ms`}
              />
              <Diagnostic
                label="Observer events"
                value={`${diagnostics.observer.replayedEventCount} replayed/deduplicated; ${diagnostics.observer.ignoredEventCount} ignored`}
              />
              <Diagnostic
                label="Last observer error"
                value={
                  diagnostics.observer.lastErrorCategory
                    ? `${diagnostics.observer.lastErrorCategory} at ${formatTime(
                        diagnostics.observer.lastErrorAt,
                      )}`
                    : "None"
                }
              />
              <Diagnostic
                label="Scheduler"
                value={`next ${formatTime(diagnostics.scheduler.nextRunAt)}; ${
                  diagnostics.scheduler.lastRunOutcome ?? "not run"
                }`}
              />
              <Diagnostic
                label="Missed-run recovery"
                value={formatTime(diagnostics.scheduler.missedRunRecoveredAt)}
              />
              <Diagnostic
                label="Reports"
                value={`facts ${formatTime(
                  diagnostics.reports.lastFactualReportAt,
                )}; narrative ${diagnostics.reports.lastNarrativeOutcome ?? "none"}`}
              />
              <Diagnostic
                label="Runtime"
                value={`${diagnostics.runtime.application} ${diagnostics.runtime.version} · ${diagnostics.runtime.node}`}
              />
            </dl>
            <ul className="retained-counts" aria-label="Retained record counts">
              {diagnostics.retainedCounts.map((item) => (
                <li key={item.category}>
                  <strong>{item.count}</strong>
                  <span>{item.category}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="danger-zone">
          <div>
            <label htmlFor="delete-local-date">Retained local day</label>
            <input
              id="delete-local-date"
              type="date"
              value={deleteDate}
              onChange={(event) => setDeleteDate(event.target.value)}
            />
            <button
              ref={deleteDayButton}
              className="danger-button"
              type="button"
              disabled={!deleteDate}
              onClick={() => openDialog("day")}
            >
              Delete this local day
            </button>
          </div>
          <div>
            <strong>Reset Codex Daily</strong>
            <p>Deletes all monitor-owned data and restores default preferences.</p>
            <button
              ref={deleteAllButton}
              className="danger-button"
              type="button"
              onClick={() => openDialog("all")}
            >
              Delete all local data
            </button>
          </div>
        </div>
        <p className="privacy-warning">
          Deletion never changes Codex chats. Monitoring may rediscover current thread
          metadata after it resumes.
        </p>
      </section>
      {dialog && (
        <div className="dialog-backdrop">
          <div
            ref={dialogElement}
            className="confirmation-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            aria-describedby="delete-dialog-description"
            onKeyDown={handleDialogKey}
          >
            <h2 id="delete-dialog-title">
              {dialog === "day" ? `Delete ${deleteDate}?` : "Delete all local data?"}
            </h2>
            <p id="delete-dialog-description">
              This affects Codex Daily only. Type <strong>{expectedConfirmation}</strong>{" "}
              to confirm. This cannot be undone from the app.
            </p>
            <form onSubmit={(event) => void confirmDeletion(event)}>
              <label>
                Confirmation
                <input
                  ref={confirmationInput}
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  autoComplete="off"
                />
              </label>
              {deletionError && (
                <p className="inline-notice" role="alert">{deletionError}</p>
              )}
              <div className="dialog-actions">
                <button type="button" className="secondary-button" onClick={closeDialog}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="danger-button"
                  disabled={deleting || confirmation !== expectedConfirmation}
                >
                  {deleting ? "Deleting…" : "Delete local data"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </article>
  );
}

function Diagnostic({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "never";
}
