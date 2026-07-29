import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ReportSchedule, ReportSchedulerState } from "../../shared/report";
import {
  getReportSettings,
  saveReportSettings,
} from "../api/report-client";

const defaults: ReportSchedule = {
  time: "18:00",
  timezone: "Europe/Berlin",
  narrativeEnabled: false,
};

export function SettingsPage() {
  const [form, setForm] = useState(defaults);
  const [state, setState] = useState<ReportSchedulerState | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getReportSettings()
      .then((result) => {
        setState(result);
        setForm(result.schedule);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "Settings could not load."),
      );
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setStatus(null);
    setError(null);
    try {
      const result = await saveReportSettings(form);
      setState(result);
      setForm(result.schedule);
      setStatus("Report schedule saved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Settings could not be saved.");
    }
  }
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
        <label>
          Evening report time
          <input
            type="time"
            required
            value={form.time}
            onChange={(event) => setForm({ ...form, time: event.target.value })}
          />
        </label>
        <label>
          IANA timezone
          <input
            required
            value={form.timezone}
            onChange={(event) => setForm({ ...form, timezone: event.target.value })}
            placeholder="Europe/Berlin"
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={form.narrativeEnabled}
            onChange={(event) =>
              setForm({ ...form, narrativeEnabled: event.target.checked })
            }
          />
          Add optional Codex-generated interpretation
        </label>
        <button className="secondary-button" type="submit">Save report settings</button>
        {status && <p role="status">{status}</p>}
        {error && <p className="inline-notice" role="alert">{error}</p>}
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
    </article>
  );
}
